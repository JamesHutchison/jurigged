import dis
import inspect
import linecache
import os
import time
from itertools import count
from types import CodeType, SimpleNamespace

from jurigged.live import watch
from jurigged.codetools import CodeFile, FunctionDefinition
from jurigged.register import Registry

from .common import TemporaryModule


_counter = count()
SNIPPET_DIR = os.path.join(
    os.path.dirname(__file__), "snippets", "hotreload"
)
pause = 0.2


def _snippet_source(name):
    return open(os.path.join(SNIPPET_DIR, f"{name}.py")).read()


def _write_file(path, contents):
    with open(path, "w") as f:
        f.write(contents)
        f.flush()
        os.fsync(f.fileno())


def _start_hot_module(main_name):
    tmod = TemporaryModule()
    module_name = f"hot_reload_suite_{next(_counter)}"
    filename = f"{module_name}.py"
    module_path = tmod.rel(filename)
    _write_file(module_path, _snippet_source(main_name))

    registry = Registry()
    watcher = watch(pattern=tmod.rel("*.py"), registry=registry, debounce=0)
    module = __import__(module_name)

    return SimpleNamespace(
        tmod=tmod,
        module_name=module_name,
        filename=filename,
        module=module,
        watcher=watcher,
    )


def _apply_change(ctx, updated_name):
    _write_file(ctx.tmod.rel(ctx.filename), _snippet_source(updated_name))
    time.sleep(pause)


def _assert_debugger_view_matches_runtime(fn, expected_firstlineno):
    filename = fn.__code__.co_filename
    linecache.checkcache(filename)
    all_lines = linecache.getlines(filename)
    src_lines, src_start = inspect.getsourcelines(fn)

    assert fn.__code__.co_firstlineno == expected_firstlineno
    assert src_start == expected_firstlineno
    assert all_lines[src_start - 1 : src_start - 1 + len(src_lines)] == src_lines


def _assert_line_markers_present(fn, expected_markers):
    filename = fn.__code__.co_filename
    linecache.checkcache(filename)
    cached_lines = linecache.getlines(filename)

    def _collect_line_numbers(code):
        numbers = {
            lineno
            for _, lineno in dis.findlinestarts(code)
            if lineno is not None and lineno >= code.co_firstlineno
        }
        for const in code.co_consts:
            if isinstance(const, CodeType):
                numbers |= _collect_line_numbers(const)
        return numbers

    line_numbers = _collect_line_numbers(fn.__code__)
    for lineno, text in expected_markers:
        assert lineno in line_numbers
        assert cached_lines[lineno - 1].strip() == text


def test_decorated_function_body_update_only_updates_body():
    ctx = _start_hot_module("decorated_body_main")
    try:
        assert ctx.module.work(3) == 7
        assert ctx.module.decoration_count == 1

        _apply_change(ctx, "decorated_body_updated")

        assert ctx.module.work(3) == 16
        assert ctx.module.decoration_count == 1
    finally:
        ctx.watcher.stop()
        ctx.watcher.join()


def test_changing_decorator_updates_decorated_behavior():
    ctx = _start_hot_module("decorator_change_main")
    try:
        existing_ref = ctx.module.work
        assert ctx.module.work(3) == 7
        assert existing_ref(3) == 7

        _apply_change(ctx, "decorator_change_updated")

        assert ctx.module.work(3) == 9
        assert existing_ref(3) == 9
    finally:
        ctx.watcher.stop()
        ctx.watcher.join()


def test_class_and_module_definitions_are_reflected_over_multiple_changes():
    ctx = _start_hot_module("class_module_main")
    try:
        greeter = ctx.module.Greeter()
        assert ctx.module.marker() == "v1"
        assert greeter.message() == "hello"
        assert ctx.module.Greeter.kind == "plain"

        _apply_change(ctx, "class_module_updated")
        assert ctx.module.marker() == "v2"
        assert greeter.message() == "hello!!!"
        assert ctx.module.Greeter.kind == "excited"
        assert ctx.module.added() == "new"

        _apply_change(ctx, "class_module_updated2")
        assert ctx.module.marker() == "v3"
        assert greeter.message() == "good day"
        assert ctx.module.Greeter.kind == "formal"
        assert ctx.module.added() == "newer"
    finally:
        ctx.watcher.stop()
        ctx.watcher.join()


def test_new_calls_update_but_existing_inflight_calls_keep_old_code():
    ctx = _start_hot_module("inflight_main")
    try:
        inflight = ctx.module.stream(3)
        assert next(inflight) == 4

        _apply_change(ctx, "inflight_updated")

        assert next(inflight) == 13
        updated = ctx.module.stream(3)
        assert next(updated) == 30
        assert next(updated) == 300
    finally:
        ctx.watcher.stop()
        ctx.watcher.join()


def test_line_numbers_do_not_drift_after_distinct_edits():
    tmod = TemporaryModule()
    module_name = f"hot_reload_line_numbers_{next(_counter)}"
    filename = f"{module_name}.py"
    module_path = tmod.rel(filename)
    _write_file(module_path, _snippet_source("line_numbers_main"))

    module = __import__(module_name)
    codefile = CodeFile(module_path, module_name=module_name)
    codefile.associate(module)

    def _apply_merge_change(updated_name):
        _write_file(module_path, _snippet_source(updated_name))
        updated = CodeFile(module_path, module_name=module_name)
        codefile.merge(updated, order="new")
        return next(
            defn
            for defn in codefile.root.walk()
            if isinstance(defn, FunctionDefinition)
            and defn.name == "keep_line_numbers_stable"
        )

    assert module.keep_line_numbers_stable() == 11
    _assert_debugger_view_matches_runtime(
        module.keep_line_numbers_stable, 1
    )
    _assert_line_markers_present(
        module.keep_line_numbers_stable,
        [
            (1, "def keep_line_numbers_stable():"),
            (4, "def inner():"),
            (5, "return base + 1"),
        ],
    )

    # Change only nested function internals: first line should not drift.
    stable_fn = _apply_merge_change("line_numbers_change_nested")
    assert module.keep_line_numbers_stable() == 12
    _assert_debugger_view_matches_runtime(
        module.keep_line_numbers_stable, 1
    )
    assert stable_fn.stashed.lineno == 1
    _assert_line_markers_present(
        module.keep_line_numbers_stable,
        [
            (1, "def keep_line_numbers_stable():"),
            (4, "def inner():"),
            (5, "return base + 2"),
        ],
    )

    # Change lines above the function: first line should move to match file.
    stable_fn = _apply_merge_change("line_numbers_change_preamble")
    assert module.keep_line_numbers_stable() == 12
    _assert_debugger_view_matches_runtime(
        module.keep_line_numbers_stable, 5
    )
    assert stable_fn.stashed.lineno == 5
    _assert_line_markers_present(
        module.keep_line_numbers_stable,
        [
            (5, "def keep_line_numbers_stable():"),
            (8, "def inner():"),
            (9, "return base + 2"),
        ],
    )

    # Change nested internals again after a line shift.
    stable_fn = _apply_merge_change("line_numbers_change_nested_again")
    assert module.keep_line_numbers_stable() == 13
    _assert_debugger_view_matches_runtime(
        module.keep_line_numbers_stable, 5
    )
    assert stable_fn.stashed.lineno == 5
    _assert_line_markers_present(
        module.keep_line_numbers_stable,
        [
            (5, "def keep_line_numbers_stable():"),
            (8, "def inner():"),
            (9, "value = base + 3"),
            (10, "return value"),
        ],
    )


def test_complex_nested_and_decorated_updates_keep_debugger_line_alignment():
    ctx = _start_hot_module("complex_main")
    try:
        first_ref = ctx.module.pipeline
        assert first_ref(2) == "v1:9"

        _apply_change(ctx, "complex_updated")

        second_ref = ctx.module.pipeline
        assert second_ref(2) == "v2:44"
        assert first_ref(2) == "v2:44"

        original_pipeline = inspect.unwrap(second_ref)
        _assert_debugger_view_matches_runtime(
            original_pipeline, expected_firstlineno=14
        )
        _assert_line_markers_present(
            original_pipeline,
            [
                (14, "@tag"),
                (15, "def pipeline(value):"),
                (18, "def middle(multiplier):"),
                (21, "def leaf(offset):"),
            ],
        )
    finally:
        ctx.watcher.stop()
        ctx.watcher.join()


def test_external_io_hot_reload_handles_ten_distinct_changes_without_drift():
    ctx = _start_hot_module("io_chain_01")
    try:
        def _await_pipeline(expected, timeout=3.0):
            deadline = time.time() + timeout
            while time.time() < deadline:
                if ctx.module.pipeline(3) == expected:
                    return
                time.sleep(0.05)
            assert ctx.module.pipeline(3) == expected

        expected_outputs = [
            "s1:8",
            "s1:12",
            "s1:17",
            "s4:17",
            "s4:20",
            "s4:21",
            "s4:26",
            "s8:18",
            "s8:15",
            "final:26",
        ]
        assert ctx.module.pipeline(3) == expected_outputs[0]

        for change_index in range(2, 11):
            _apply_change(ctx, f"io_chain_{change_index:02d}")
            _await_pipeline(expected_outputs[change_index - 1])

        # Re-check at the end to ensure the module still reflects latest logic.
        assert ctx.module.pipeline(3) == "final:26"
        assert ctx.module.TAG == "final"
        assert ctx.module.DECORATOR_BONUS == 7

        _assert_debugger_view_matches_runtime(
            ctx.module.raw_pipeline, expected_firstlineno=16
        )
        _assert_line_markers_present(
            ctx.module.raw_pipeline,
            [
                (16, "def raw_pipeline(value):"),
                (19, "def inner(multiplier):"),
                (20, "def leaf(offset):"),
                (21, "return seed * multiplier + offset"),
            ],
        )
    finally:
        ctx.watcher.stop()
        ctx.watcher.join()
