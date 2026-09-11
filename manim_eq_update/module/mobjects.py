from __future__ import annotations

import warnings

from manim import *
from reactive_manim import *


__all__ = [
    "write_text",
    "axes",
    "SizedStealthTip",
    "change",
    "copy_eq",
    "equation",
    "evolve",
    "part",
    "TransformInStages",
    "ProblemScene",
]


def _dynamic_family(mobject):
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message="This method is not guaranteed to stay around.*",
            category=DeprecationWarning,
        )
        return mobject.get_dynamic_family()


def write_text(
    content: str,
    font: str = "Malgun Gothic",
    font_size: float = 72,
    color=WHITE,
    **text_kwargs,
) -> VGroup:
    """글자와 글자 내부 획을 정렬한 VGroup을 반환합니다."""
    text = Text(
        content,
        font=font,
        font_size=font_size,
        color=color,
        **text_kwargs,
    )

    pieces = []

    for char_index, char in enumerate(text.family_members_with_points()):
        subpaths = sorted(
            char.get_subpaths(),
            key=lambda path: (
                -path[:, 1].mean(),
                path[:, 0].mean(),
            ),
        )

        for subpath in subpaths:
            piece = VMobject(color=color).set_points_as_corners(subpath)
            piece.char_index = char_index
            pieces.append(piece)

    return VGroup(*pieces)


class SizedStealthTip(StealthTip):
    def __init__(
        self,
        length=0.4,
        custom_width=0.08,
        **kwargs,
    ):
        super().__init__(length=length, **kwargs)
        self.stretch_to_fit_width(length)
        self.stretch_to_fit_height(custom_width)


class axes(Axes):
    def __init__(self, *args, **kwargs):
        axis_config = {
            "color": BLACK,
            "stroke_width": 1.4,
            "include_numbers": False,
            "include_ticks": False,
            "tip_shape": SizedStealthTip,
            "tip_height": 0.2,
            "tip_style": {"custom_width": 0.12},
        }

        axis_config.update(
            kwargs.pop(
                "axis_config",
                {},
            )
        )

        super().__init__(
            *args,
            axis_config=axis_config,
            **kwargs,
        )

        self.x_label = MathTex(
            "x",
            color=BLACK,
        ).next_to(
            self.x_axis.get_end(),
            0.01 * LEFT + DOWN,
            buff=0.15,
        )

        self.y_label = MathTex(
            "y",
            color=BLACK,
        ).next_to(
            self.y_axis.get_end(),
            0.01 * DOWN + LEFT,
            buff=0.15,
        )

        self.origin_label = Tex(
            "O",
            color=BLACK,
        ).next_to(
            self.c2p(0, 0),
            LEFT + DOWN,
            buff=0.1,
        )

        self.add(
            self.x_label,
            self.y_label,
            self.origin_label,
        )


# ============================================================
# TransformInStages
# ============================================================
#
# 핵심:
#
# N -> 1일 때 Reactive Manim 원래 Transform은 그대로 둔다.
#
#     a -> 24
#     b -> 24
#     c -> 24
#
# 즉 전부 끝까지 24로 포개지게 한다.
#
# 그 뒤 clean_up_from_scene 단계에서
# keeper가 아닌 merge-source transform_container만 제거한다.
#
# 따라서:
#
#     24 24 24  ->  24
#
# 가 된다.
#
# 1 -> N clone(source_id)은 target_id merge가 아니므로
# cleanup 대상이 아니다.
# ============================================================


_ReactiveTransformInStages = TransformInStages


def _attach_merge_container_cleanup(animation):
    """
    Reactive Manim의 원래 Transform 애니메이션은 전혀 변경하지 않는다.

    N -> 1 merge source들을 기억해 두었다가,
    전체 Transform이 100% 완료된 뒤 clean_up_from_scene에서
    그 source들의 transform_container만 제거한다.

    결과:
        모든 source가 target까지 실제로 Transform되어 포개짐
        -> keeper 하나를 제외한 중복 container 즉시 remove

    branch(source_id)는 target_id merge가 아니므로 영향을 받지 않는다.
    """

    descriptor = animation.config.transform_descriptor
    source_graph = descriptor.source_graph
    target_graph = descriptor.target_graph

    merge_source_ids = []

    for source in source_graph.dynamic_mobjects:
        target_id = getattr(
            source,
            "target_id",
            None,
        )

        if target_id is None:
            continue

        # source 자신이 target graph에도 그대로 살아 있다면
        # remover/merge source가 아니므로 건드리지 않는다.
        if target_graph.contains(source.id):
            continue

        # Reactive Manim이 이 source의 실제 target을
        # target_id 객체로 해석하는 경우만 merge로 인정.
        target = descriptor.find_target_dynamic_mobject(source.id)

        if target is None:
            continue

        if target.id != target_id:
            continue

        # 해당 itinerary/container가 실제로 존재하는 경우만.
        if source.id not in animation.config.transform_containers:
            continue

        merge_source_ids.append(source.id)

    if not merge_source_ids:
        return animation

    # progress()/from_copy()가 이미 넣어둔 원래 cleanup을 보존한다.
    original_clean_functions = list(animation.clean_functions)

    def remove_merge_containers(scene):
        # AbstractDynamicTransform.clean_up_from_scene()은 이 함수들이
        # 실행되기 직전에 모든 transform_container를 scene에 다시 add한다.
        # 따라서 여기에서 merge source container만 제거하면
        # 실제 survivor target 하나만 남는다.
        for source_id in merge_source_ids:
            container = animation.config.transform_containers.get(source_id)

            if container is None:
                continue

            # 혹시 같은 cleanup frame에서 한 프레임 보이는 것을 방지.
            container.set_opacity(0)

            # reactive_manim이 보존해 둔 원래 Scene.remove 사용.
            scene.scene_remove(container)

    animation.clean_functions = (
        original_clean_functions
        + [remove_merge_containers]
    )

    return animation


from contextlib import contextmanager


@contextmanager
def _temporary_merge_links(source, target):
    source_parts = _ReactiveTransformInStages.extract_subgraph(source).dynamic_mobjects
    target_parts = _ReactiveTransformInStages.extract_subgraph(target).dynamic_mobjects
    by_id = {p.id: p for p in source_parts}
    saved = {}
    try:
        for target_part in target_parts:
            for sid in getattr(target_part, "_change_source_ids", ())[1:]:
                if sid in by_id:
                    src = by_id[sid]
                    if sid not in saved:
                        saved[sid] = src.target_id
                    _set_link(src, "target_id", target_part.id)
        yield
    finally:
        for sid, previous in saved.items():
            _set_link(by_id[sid], "target_id", previous)


class TransformInStages(_ReactiveTransformInStages):
    """
    기존 Reactive Manim API 그대로 사용:

        TransformInStages.progress(eq)
        TransformInStages.from_copy(eq1, eq2)
        TransformInStages.replacement_transform(eq1, eq2)

    N -> 1 merge일 때만 애니메이션 종료 cleanup을 추가한다.
    """

    @classmethod
    def progress(
        cls,
        mobject,
        config=None,
        **kwargs,
    ):
        # progress는 scene.add()가 저장한 수정 전 그래프를 사용한다.
        selection = _ReactiveTransformInStages.extract_subgraph(mobject)
        managers = [SceneManager.scene_manager().graph_manager(p.graph)
                    for p in selection.dynamic_mobjects]
        progress_managers = [m.progress_manager for m in managers if m.has_progress_manager()]
        if progress_managers:
            source = progress_managers[0].source_graph.dynamic_mobjects
            with _temporary_merge_links(source, mobject):
                animation = super().progress(mobject, config=config, **kwargs)
        else:
            animation = super().progress(mobject, config=config, **kwargs)

        return _attach_merge_container_cleanup(
            animation
        )

    @classmethod
    def from_copy(
        cls,
        source_mobject,
        target_mobject,
        config=None,
        **kwargs,
    ):
        with _temporary_merge_links(source_mobject, target_mobject):
            animation = super().from_copy(
                source_mobject, target_mobject, config=config, **kwargs
            )

        return _attach_merge_container_cleanup(
            animation
        )

    @classmethod
    def replacement_transform(
        cls,
        source_mobject,
        target_mobject,
        config=None,
        **kwargs,
    ):
        with _temporary_merge_links(source_mobject, target_mobject):
            animation = super().replacement_transform(
                source_mobject, target_mobject, config=config, **kwargs
            )

        return _attach_merge_container_cleanup(
            animation
        )


# ============================================================
# change
# ============================================================

def _ordered_parts(mobject):
    """get_dynamic_family()는 set 순서이므로 화면 순서를 사용한다."""
    return sorted(
        (p for p in _dynamic_family(mobject) if p.has_direct_points()),
        key=lambda p: (float(p.get_center()[0]), -float(p.get_center()[1]), str(p.id)),
    )


def _set_link(mobject, name, value):
    locked = mobject.reactive_lock
    try:
        mobject.reactive_lock = True
        setattr(mobject, name, value)
    finally:
        mobject.reactive_lock = locked


def copy_eq(eq):
    """모양/ID는 유지하되 이전 단계의 변환 지시를 지운 독립 사본."""
    result = eq.copy()
    for p in _dynamic_family(result):
        _set_link(p, "source_id", None)
        _set_link(p, "target_id", None)
        p.__dict__.pop("_change_source_ids", None)
    return result


def _copy_input(value, seen=None):
    if seen is None:
        seen = set()
    if isinstance(value, DynamicMobject):
        ids = {p.id for p in _dynamic_family(value)}
        result = value.clone() if ids & seen else value.copy()
        seen.update(p.id for p in _dynamic_family(result))
        return result
    if isinstance(value, (list, tuple)):
        return [_copy_input(v, seen) for v in value]
    return value


def equation(*terms, **kwargs):
    """MathTex처럼 사용. 입력 객체를 복사하여 앞 식의 부모/ID를 보호한다."""
    seen = set()
    return MathTex(*[_copy_input(t, seen) for t in terms], **kwargs)


def change(old, new):
    """1→1, N→1, 1→N 및 구조 변환. old의 값/부모/링크는 수정하지 않는다.

    change([a, b], 6), change(x, Fraction(1, 2))
    여러 입력의 추적 정보는 결과 쪽에만 보관한다.
    """
    originals = list(old) if isinstance(old, (list, tuple)) else [old]
    if not originals or any(not isinstance(o, DynamicMobject) for o in originals):
        raise ValueError("change()에는 하나 이상의 Reactive Manim 객체가 필요합니다.")
    sources = []
    seen = set()
    for original in originals:
        for p in _ordered_parts(original):
            if p.id not in seen:
                sources.append(p)
                seen.add(p.id)
    if not sources:
        raise ValueError("change()에서 변환할 글자나 선을 찾지 못했습니다.")
    if isinstance(new, DynamicMobject):
        result = new.clone()
    elif isinstance(new, (list, tuple)):
        result = equation(*new).clone()
    else:
        result = MathTex(str(new))[0].clone()
    for p in _dynamic_family(result):
        _set_link(p, "source_id", None)
        _set_link(p, "target_id", None)
        p.__dict__.pop("_change_source_ids", None)
    targets = _ordered_parts(result)
    if not targets:
        raise ValueError("change()의 새 값에 표시할 글자나 선이 없습니다.")
    links = [[] for _ in targets]
    for i, target in enumerate(targets):
        links[i].append(sources[i * len(sources) // len(targets)].id)
    used = {sid for group in links for sid in group}
    for i, source in enumerate(sources):
        if source.id not in used:
            links[i * len(targets) // len(sources)].append(source.id)
    for target, ids in zip(targets, links):
        _set_link(target, "source_id", ids[0])
        target._change_source_ids = tuple(ids)
    result.set_color(originals[0].get_color(), family=True)
    return result


def _path_tokens(path):
    if isinstance(path, int):
        return [path]
    if isinstance(path, (tuple, list)):
        tokens = list(path)
    elif isinstance(path, str):
        tokens = path.split(".")
    else:
        raise TypeError("경로는 정수, '2.base', 또는 (2, 'base') 형식입니다.")
    if not tokens or any(t == "" for t in tokens):
        raise ValueError("빈 경로는 사용할 수 없습니다.")
    return [int(t) if isinstance(t, str) and t.lstrip("-").isdigit() else t for t in tokens]


def part(eq, path):
    """part(eq, '3.base.inner.exponent') 또는 part(eq, (3, 'base'))."""
    obj = eq
    try:
        for token in _path_tokens(path):
            obj = obj[token] if isinstance(token, int) else getattr(obj, token)
    except (IndexError, AttributeError, TypeError) as exc:
        raise ValueError(f"수식 경로를 찾을 수 없습니다: {path!r}") from exc
    return obj


def _put(eq, path, value):
    tokens = _path_tokens(path)
    parent = eq if len(tokens) == 1 else part(eq, tokens[:-1])
    key = tokens[-1]
    if isinstance(key, int):
        parent[key] = value
    else:
        if not hasattr(parent, key):
            raise ValueError(f"수식 경로를 찾을 수 없습니다: {path!r}")
        setattr(parent, key, value)


def evolve(eq, replacements=None, *, build=None, inserts=(), deletes=()):
    """원본을 유지하고 다음 식을 반환한다. 자동 재생하지 않는다.

    eq1_1 = evolve(eq1, {'2.exponent': 2})
    eq2 = evolve(eq1_1, build=lambda q: MathTex(q[0], Fraction(q[2], q[1])))

    replacements/deletes는 수정 전 경로, inserts는 앞 삽입이 반영된 순서.
    build는 독립 사본을 받는다. 외부 eq를 직접 수정하지 말 것.
    """
    if not isinstance(eq, DynamicMobject):
        raise TypeError("evolve()에는 Reactive Manim 수식이 필요합니다.")
    if build is not None and (replacements or inserts or deletes):
        raise ValueError("build와 replacements/inserts/deletes는 별도 단계로 사용하세요.")
    result = copy_eq(eq)
    if build is not None:
        result = build(result)
        if not isinstance(result, DynamicMobject):
            raise TypeError("build는 새 Reactive Manim 수식을 반환해야 합니다.")
        return result
    updates = list((replacements or {}).items())
    paths = [_path_tokens(path) for path, _ in updates]
    for i, p in enumerate(paths):
        for q in paths[i + 1:]:
            if p[:len(q)] == q or q[:len(p)] == p:
                raise ValueError("부모와 자식 경로를 동시에 바꿀 수 없습니다. 단계를 나누세요.")
    values = [(path, change(part(result, path), value)) for path, value in updates]
    for path, value in values:
        _put(result, path, value)
    if deletes:
        indices = set()
        for index in deletes:
            if not isinstance(index, int) or not -len(result) <= index < len(result):
                raise IndexError(f"삭제 인덱스 범위 초과: {index!r}")
            indices.add(index % len(result))
        result.terms = [t for i, t in enumerate(result.terms) if i not in indices]
    for index, value in inserts:
        if not isinstance(index, int) or not 0 <= index <= len(result):
            raise IndexError(f"삽입 인덱스 범위 초과: {index!r}")
        result.insert(index, _copy_input(value))
        if not isinstance(value, DynamicMobject):
            result[index].set_color(result.get_color(), family=True)
    return result


# ============================================================
# ProblemScene
# ============================================================

class ProblemScene(MovingCameraScene):
    margin = 0.5
    gap = 0.5
    problem_width = 4.0
    font_size = 15

    def setup(self):
        super().setup()

        self.camera.background_color = WHITE

        MathTex.set_default(
            color=BLACK,
            font_size=self.font_size,
        )

        self.width = (
            self.camera.frame.get_width()
        )

        self.height = (
            self.camera.frame.get_height()
        )

        self.area_height = (
            self.height
            - 2 * self.margin
        )

        self.solution_width = (
            self.width
            - 2 * self.margin
            - self.gap
            - self.problem_width
        )

        self.problem_coord = np.array([
            -self.width * 0.5
            + self.margin,
            self.height * 0.5
            - self.margin,
            0,
        ])

        self.solution_coord = (
            self.problem_coord
            + np.array([
                self.problem_width
                + self.gap,
                0,
                0,
            ])
        )

    def create_layout_areas(
        self,
        show_border=True,
    ):
        problem_area = Rectangle(
            width=self.problem_width,
            height=self.area_height,
            color=BLUE,
            stroke_width=2,
        ).move_to(
            self.problem_coord,
            aligned_edge=UL,
        )

        solution_area = Rectangle(
            width=self.solution_width,
            height=self.area_height,
            color=GREEN,
            stroke_width=2,
        ).move_to(
            self.solution_coord,
            aligned_edge=UL,
        )

        if show_border:
            self.add(
                problem_area,
                solution_area,
            )

        return (
            problem_area,
            solution_area,
        )
