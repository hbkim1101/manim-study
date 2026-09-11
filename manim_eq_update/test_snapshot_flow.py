"""수식 정의와 재생을 분리하는 SolutionFlow.

모든 편집 메서드는 새 수식을 반환합니다. 반환값을 eq1_1처럼 받으세요.
화면에는 수식의 일반 VMobject 사본을 표시하여 Reactive 그래프와 분리합니다.
따라서 재생, 배치, 분기 후에도 원본 식을 다시 사용할 수 있습니다.
"""
from dataclasses import dataclass

from manim import (
    VGroup, VMobject, Transform, FadeIn, FadeOut, AnimationGroup,
    DOWN, UL, LEFT, MED_LARGE_BUFF,
)
from .mobjects import (
    change, copy_eq, equation, evolve, part, _ordered_parts, _put, _dynamic_family,
    _path_tokens, MathTex, Term, Paren, DynamicMobject,
)

__all__ = ["SolutionFlow"]


@dataclass
class _Step:
    parent: object
    mode: str
    external: tuple = ()


class _SnapshotTransition(AnimationGroup):
    def __init__(self, scene, source_display, target_display, animations,
                 temporary, *, keep_source, run_time, lag_ratio):
        self.owner_scene = scene
        self.source_display = source_display
        self.target_display = target_display
        self.temporary = temporary
        self.keep_source = keep_source
        super().__init__(*animations, run_time=run_time, lag_ratio=lag_ratio)

    def begin(self):
        if not self.keep_source:
            self.owner_scene.remove(self.source_display)
        super().begin()

    def clean_up_from_scene(self, scene):
        super().clean_up_from_scene(scene)
        scene.remove(self.group, *self.temporary)
        scene.add(self.target_display)


def _display(eq):
    parts = _ordered_parts(eq)
    # direct_submobjects()에는 DynamicMobject 자식이 포함되지 않는다.
    pieces = {p.id: p.direct_submobjects().copy() for p in parts}
    return VGroup(*pieces.values()), pieces


def _tex_key(obj):
    return ''.join(obj.get_tex_string().split())


def _is_power(obj):
    return (isinstance(obj, Term) and obj.exponent is not None
            and obj.subscript is None and obj._parentheses in (None, False))


def _require_power(obj, path):
    if not _is_power(obj):
        raise ValueError(f"{path!r}는 지수가 있는 Term 구조가 아닙니다.")


def _nested_power(obj):
    if not _is_power(obj):
        return False
    inner = obj.base
    while isinstance(inner, Paren):
        inner = inner.inner
    return _is_power(inner)


def _power_pair(eq, left, right):
    return (right == left + 2 and _is_power(eq[left]) and _is_power(eq[right])
            and _tex_key(eq[left + 1]) in (r'\times', r'\cdot')
            and _tex_key(eq[left].base) == _tex_key(eq[right].base))


def _unique_candidate(candidates, operation):
    if not candidates:
        raise ValueError(f"{operation}: 변환 가능한 최상위 항이 없습니다. 중첩 항은 위치를 지정하세요.")
    if len(candidates) != 1:
        raise ValueError(f"{operation}: 후보가 여러 개입니다: {candidates}. 위치를 지정하세요.")
    return candidates[0]


class SolutionFlow:
    def __init__(self, scene, pdf_path=None, problem_number=None, *,
                 run_time=1.0, pause=0.4, buff=MED_LARGE_BUFF,
                 camera_width=4.0, camera_run_time=0.5):
        self.scene = scene
        self.pdf_path = pdf_path
        self.problem_number = problem_number
        self.run_time = run_time
        self.pause = pause
        self.buff = buff
        self.camera_width = camera_width
        self.camera_run_time = camera_run_time
        self.steps = {}
        self.displays = {}
        self.shown_equations = {}
        self.sequence = []
        self.current = None

    def _register(self, source, target, same_line, external=()):
        self.steps[id(target)] = _Step(source, "replace" if same_line else "copy", tuple(external))
        return target

    def evolve(self, eq, replacements=None, *, build=None, inserts=(),
               deletes=(), same_line=False):
        result = evolve(eq, replacements, build=build, inserts=inserts, deletes=deletes)
        return self._register(eq, result, same_line)

    def rewrite(self, eq, path, transform, *, same_line=False):
        """선택한 항만 재조합. 콜백은 그 항의 독립 사본을 받는다.

        flow.rewrite(eq, 2, lambda p: Fraction(p.denominator, p.numerator))
        나머지 항의 재나열이 필요 없으며 원본은 유지된다.
        """
        if not callable(transform):
            raise TypeError("transform에는 선택 항을 받아 새 항을 반환하는 함수를 넣으세요.")
        selected = part(eq, path)
        if not isinstance(selected, DynamicMobject):
            raise ValueError(f"재조합할 수식 항이 아닙니다: {path!r}")
        colors = {p.id: p.get_color() for p in _ordered_parts(eq)}
        value = transform(copy_eq(selected))
        if value is None:
            raise ValueError("rewrite 콜백은 새 항을 반환해야 합니다.")
        if isinstance(value, (list, tuple)):
            value = equation(*value)
        if not isinstance(value, DynamicMobject):
            value = change(selected, value)
        else:
            value = value.copy()
        value.set_color(selected.get_color(), family=True)
        result = copy_eq(eq)
        _put(result, path, value)
        # 기존 항의 개별 색은 유지하고 새 기호만 선택 항의 색을 따른다.
        for p in _ordered_parts(result):
            if p.id in colors:
                p.set_color(colors[p.id], family=True)
        return self._register(eq, result, same_line)

    def set_base(self, eq, at, value, *, same_line=False):
        """flow.set_base(eq, 3, 2): 3번 거듭제곱의 밑만 변경."""
        _require_power(part(eq, at), at)
        return self.evolve(eq, {tuple(_path_tokens(at) + ['base']): value},
                           same_line=same_line)

    def set_exponent(self, eq, at, value, *, same_line=False):
        """flow.set_exponent(eq, 3, -1): 3번 거듭제곱의 지수만 변경."""
        _require_power(part(eq, at), at)
        return self.evolve(eq, {tuple(_path_tokens(at) + ['exponent']): value},
                           same_line=same_line)

    def flatten_power(self, eq, at=None, *, same_line=False):
        r"""(a^m)^n → a^(m × (n)). 계산하지 않고 구조를 펼친다.

        flow.flatten_power(eq)       # 최상위 후보가 하나일 때 자동 선택
        flow.flatten_power(eq, 3)    # 여러 후보면 인덱스 지정
        flow.flatten_power(eq, '2.numerator')  # 중첩 위치도 지정 가능
        """
        if at is None:
            candidates = [i for i, term in enumerate(eq) if _nested_power(term)]
            at = _unique_candidate(candidates, 'flatten_power')
        if not _nested_power(part(eq, at)):
            raise ValueError(f"{at!r}는 (a^m)^n 구조가 아닙니다. Term과 Paren으로 구성하세요.")

        def expand(outer):
            inner = outer.base
            while isinstance(inner, Paren):
                inner = inner.inner
            # 각 원소를 별도 복사하여 내부 부모의 자동 재연결도 피한다.
            return Term(inner.base.copy(),
                        [inner.exponent.copy(), r'\times', Paren(outer.exponent.copy())])

        return self.rewrite(eq, at, expand, same_line=same_line)

    def combine_powers(self, eq, left=None, right=None, *, same_line=False):
        r"""a^m × a^n → a^(m+n). 명시적인 ×/·로 연결된 같은 밑만 결합.

        flow.combine_powers(eq)       # 최상위 후보 한 쌍 자동 선택
        flow.combine_powers(eq, 1, 3) # 두 항 사이에 곱셈 기호가 있어야 함
        밑의 일치는 TeX 공백을 제외한 문자열로 확인하며 기호 계산은 하지 않는다.
        """
        if (left is None) != (right is None):
            raise ValueError("left와 right를 함께 지정하거나 둘 다 생략하세요.")
        if left is None:
            candidates = [(i, i + 2) for i in range(len(eq) - 2)
                          if _power_pair(eq, i, i + 2)]
            left, right = _unique_candidate(candidates, 'combine_powers')
        if not (isinstance(left, int) and isinstance(right, int)):
            raise TypeError("combine_powers의 위치는 최상위 항의 정수 인덱스입니다.")
        n = len(eq)
        if not (-n <= left < n and -n <= right < n):
            raise IndexError("거듭제곱 위치가 수식 범위를 벗어났습니다.")
        left, right = left % n, right % n
        if not _power_pair(eq, left, right):
            raise ValueError("같은 밑의 거듭제곱 두 항이 × 또는 ·로 연결되어야 합니다.")
        q = copy_eq(eq)
        a, b = q[left], q[right]
        base = change([a.base, b.base], a.base)
        # 단일 음수일 때는 m-1, 합성식은 m+(...)로 묶어 의미를 보존한다.
        import re
        text = _tex_key(b.exponent)
        if re.fullmatch(r'-\d+(?:\.\d+)?', text):
            exponent = [a.exponent.copy(), b.exponent.copy()]
        else:
            rhs = b.exponent.copy()
            if isinstance(rhs, MathTex) and len(rhs) > 1:
                rhs = Paren(rhs)
            exponent = [a.exponent.copy(), '+', rhs]
        merged = Term(base, exponent)
        merged.set_color(a.get_color(), family=True)
        # 곱셈 기호과 오른쪽 항만 제거한다. 앞뒤의 다른 항은 그대로 둔다.
        q.terms = [*q.terms[:left], merged, *q.terms[right + 1:]]
        colors = {v.id: v.get_color() for v in _ordered_parts(eq)}
        for p in _ordered_parts(q):
            source_ids = getattr(p, '_change_source_ids', ())
            color_id = p.id if p.id in colors else (source_ids[0] if source_ids else None)
            if color_id in colors:
                p.set_color(colors[color_id], family=True)
        return self._register(eq, q, same_line)

    def change_at(self, eq, path, value, *, same_line=True):
        return self.evolve(eq, {path: value}, same_line=same_line)

    def insert(self, eq, index, value, *, same_line=True):
        """list는 한 그룹으로 삽입. 여러 최상위 항은 evolve(inserts=...) 사용."""
        return self.evolve(eq, inserts=[(index, value)], same_line=same_line)

    def append(self, eq, *values, same_line=True):
        return self.evolve(eq, inserts=[(len(eq) + i, value) for i, value in enumerate(values)],
                           same_line=same_line)

    def collapse_from(self, eq, start, value, *, stop=None, same_line=True):
        """[start:stop]을 병합. stop=None은 끝까지. 계산 결과는 사용자가 지정."""
        n = len(eq)
        if not isinstance(start, int) or not -n <= start < n:
            raise IndexError(f"합칠 시작 인덱스 범위 초과: {start!r}")
        start %= n
        stop = n if stop is None else stop
        if not isinstance(stop, int) or not start < stop <= n:
            raise IndexError("stop은 start보다 크고 수식 길이 이하여야 합니다.")
        q = copy_eq(eq)
        merged = change(list(q.terms[start:stop]), value)
        result = equation(*q.terms[:start], merged, *q.terms[stop:])
        return self._register(eq, result, same_line)

    def inject_copy(self, eq, path, source, *, inserts=(), same_line=True):
        """다른 식의 source를 복사 이동할 새 단계. 호출 즉시 재생하지 않는다."""
        q = copy_eq(eq)
        # old 자리의 값 대신 외부 source에서 출발하도록 provenance를 지정한다.
        value = source.clone()
        for p in _ordered_parts(value):
            p.__dict__.pop("_change_source_ids", None)
        _put(q, path, value)
        for index, term in inserts:
            if not isinstance(index, int) or not 0 <= index <= len(q):
                raise IndexError(f"삽입 인덱스 범위 초과: {index!r}")
            q.insert(index, term.copy() if hasattr(term, "copy") else term)
            if not hasattr(term, "get_color"):
                q[index].set_color(q.get_color(), family=True)
        return self._register(eq, q, same_line, external=(source,))

    def load_problem(self):
        if self.pdf_path is None:
            return None
        # 사용자 프로젝트의 기존 PDF 도구를 그대로 사용한다.
        from .pdf_tools import pdf_problem_image
        problem = pdf_problem_image(self.pdf_path, problem_number=self.problem_number)
        problem.scale_to_fit_width(self.scene.problem_width)
        problem.move_to(self.scene.problem_coord, aligned_edge=UL)
        self.scene.add(problem)
        self.problem = problem
        return problem

    def _origin(self):
        if hasattr(self.scene, "solution_coord"):
            return self.scene.solution_coord + 0.5 * DOWN
        return self.scene.camera.frame.get_corner(UL) + [0.5, -0.5, 0]

    def place_first(self, eq):
        eq.move_to(self._origin(), aligned_edge=UL)
        return eq

    def place_below(self, previous, eq):
        eq.next_to(previous, DOWN, aligned_edge=LEFT, buff=self.buff)
        return eq

    def stack(self, *equations):
        """같은 자리 수정은 한 행을 공유. 모든 버전의 최대 높이로 행 간격 확보."""
        if len(equations) == 1 and isinstance(equations[0], (list, tuple)):
            equations = tuple(equations[0])
        self.sequence = list(equations)
        rows = []
        row_index = {}
        for eq in equations:
            step = self.steps.get(id(eq))
            if step and step.mode == "replace" and id(step.parent) in row_index:
                index = row_index[id(step.parent)]
            else:
                index = len(rows)
                rows.append([])
            rows[index].append(eq)
            row_index[id(eq)] = index
        anchor = self._origin().copy()
        for row in rows:
            height = max(eq.height for eq in row)
            for eq in row:
                eq.move_to(anchor, aligned_edge=UL)
            anchor = anchor + (height + self.buff) * DOWN
        # 레이아웃용 그룹이며 scene.add()하지 않는다.
        return VGroup(*equations)

    def focus(self, eq):
        frame = getattr(self.scene.camera, "frame", None)
        if frame is not None:
            self.scene.play(frame.animate.move_to(eq.get_center()).set(
                width=max(self.camera_width, eq.width + 1.0)),
                run_time=self.camera_run_time)
        return eq

    def begin(self, eq=None, *, focus=True):
        if eq is None:
            if not self.sequence:
                raise ValueError("begin(eq) 또는 stack(...)을 먼저 호출하세요.")
            eq = self.sequence[0]
        if focus:
            self.focus(eq)
        display, pieces = _display(eq)
        old = self.displays.get(id(eq))
        if old:
            self.scene.remove(old[0])
        self.displays[id(eq)] = (display, pieces)
        self.shown_equations[id(eq)] = eq
        self.scene.add(display)
        self.current = eq
        if self.pause:
            self.scene.wait(self.pause)
        return eq

    def transition(self, source, target, *, same_line=None, run_time=None,
                   lag_ratio=0.0, focus=True):
        if id(source) not in self.displays:
            raise ValueError("출발 식을 begin() 또는 transition()으로 먼저 표시하세요.")
        step = self.steps.get(id(target))
        related = step is not None and step.parent is source
        replace = (related and step.mode == "replace") if same_line is None else same_line
        if replace:
            target.move_to(source.get_corner(UL), aligned_edge=UL)
        if focus:
            self.focus(target)
        source_display, source_pieces = self.displays[id(source)]
        if source_display not in self.scene.mobjects:
            raise ValueError("출발 식이 화면에 없습니다. begin(source)로 다시 표시하세요.")
        target_display, target_pieces = _display(target)
        available = dict(source_pieces)
        if related:
            for external in step.external:
                for p in _ordered_parts(external):
                    # 표시 중인 식의 사본 좌표를 우선한다.
                    matches = [pieces[p.id] for key, (display, pieces) in self.displays.items()
                               if p.id in pieces and display in self.scene.mobjects
                               and any(member is p for member in
                                       _dynamic_family(self.shown_equations[key]))]
                    if not matches:
                        raise ValueError("복사할 외부 항이 화면에 없습니다. 해당 식을 먼저 표시하세요.")
                    available[p.id] = matches[-1]
        animations, temporary, used = [], [], set()
        for p in _ordered_parts(target):
            provenance = getattr(p, "_change_source_ids", ())
            ids = provenance or ((p.id,) if p.id in available else (p.source_id,))
            ids = list(dict.fromkeys(sid for sid in ids if sid in available))
            destination = target_pieces[p.id]
            if ids:
                for sid in ids:
                    moving = available[sid].copy()
                    temporary.append(moving)
                    animations.append(Transform(moving, destination.copy()))
                    used.add(sid)
            else:
                appearing = destination.copy()
                temporary.append(appearing)
                animations.append(FadeIn(appearing))
        if replace:
            for sid, piece in source_pieces.items():
                if sid not in used:
                    disappearing = piece.copy()
                    temporary.append(disappearing)
                    animations.append(FadeOut(disappearing))
        animation = _SnapshotTransition(
            self.scene, source_display, target_display, animations, temporary,
            keep_source=not replace,
            run_time=self.run_time if run_time is None else run_time,
            lag_ratio=lag_ratio,
        )
        self.scene.play(animation)
        self.displays[id(target)] = (target_display, target_pieces)
        self.shown_equations[id(target)] = target
        self.current = target
        if self.pause:
            self.scene.wait(self.pause)
        return target

    def play_linear(self, equations=None, *, begin=True):
        sequence = self.sequence if equations is None else list(equations)
        if not sequence:
            return
        if begin:
            self.begin(sequence[0])
        for source, target in zip(sequence, sequence[1:]):
            self.transition(source, target)

    def fade_next(self, previous, eq):
        """별개 식을 표시하는 재생 메서드. 수식 정의 후 호출한다."""
        self.place_below(previous, eq)
        self.focus(eq)
        display, pieces = _display(eq)
        self.scene.play(FadeIn(display), run_time=self.run_time)
        self.displays[id(eq)] = (display, pieces)
        self.shown_equations[id(eq)] = eq
        self.current = eq
        return eq

    def finish(self, wait=1.0):
        if wait:
            self.scene.wait(wait)
