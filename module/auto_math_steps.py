r"""LaTeX -> structure-aware Manim animations (Manim Community 0.19+).

Native LaTeX layout revision: full-expression rendering, no manual glyph layout.

Notebook:
    from auto_math_steps import AutoMathSteps
    solution = AutoMathSteps(r'4', r'(2^2)', color=BLACK)
    solution.play(self)

Render included demo:
    manim -ql auto_math_steps.py AutoMathDemo

Supported: numbers, single-letter symbols, +, -, explicit/implicit products,
\\times, \\cdot, powers, \\frac, parentheses, and one equality per row
(including a leading '=' on continuation rows).
This is a bounded syntax parser and visual correspondence engine, not a CAS:
it does not prove that consecutive equations are mathematically equivalent.
It uses standard Manim objects, independently of reactive-manim tracking.
"""
from __future__ import annotations
from dataclasses import dataclass, field
import re
from pathlib import Path
import xml.etree.ElementTree as ET
import numpy as np
import manim as mn


@dataclass(eq=False)
class Expr:
    kind: str
    children: list = field(default_factory=list)
    value: str = ''
    mob: object = field(default=None, repr=False)
    start: int = 0
    end: int = 0
    wrap: bool = False

    def key(self):
        return self.kind, self.value, tuple(c.key() for c in self.children)


class LatexSyntaxError(ValueError):
    pass


class Parser:
    def __init__(self, text):
        if not isinstance(text, str):
            raise TypeError('Pass raw LaTeX strings, not rendered MathTex objects.')
        self.text = text
        pattern = r'\\(?:frac|times|cdot|left|right|quad|qquad)\b|\\[,;!]|\d+(?:\.\d+)?|[a-zA-Z]|[{}()^+\-=*]'
        self.tokens, self.spans = [], []
        pos, delimiter_start = 0, None
        for m in re.finditer(pattern, text):
            if text[pos:m.start()].strip():
                raise LatexSyntaxError(f'Unsupported LaTeX near {text[pos:m.start()]!r}')
            pos = m.end()
            t = m.group()
            if t in (r'\left', r'\right'):
                delimiter_start = m.start()
                continue
            if t in (r'\quad', r'\qquad', r'\,', r'\;', r'\!'):
                continue
            if delimiter_start is not None and t not in ('(', ')'):
                raise LatexSyntaxError('Only round \\left/\\right delimiters are supported.')
            self.tokens.append(t)
            self.spans.append((delimiter_start if delimiter_start is not None else m.start(), m.end()))
            delimiter_start = None
        if text[pos:].strip() or delimiter_start is not None:
            raise LatexSyntaxError('Incomplete or unsupported LaTeX at end of expression.')
        self.i = 0

    def peek(self):
        return self.tokens[self.i] if self.i < len(self.tokens) else None

    def take(self, expected=None):
        t = self.peek()
        if t is None or (expected is not None and t != expected):
            raise LatexSyntaxError(f'Expected {expected or "expression"}, got {t!r}')
        self.i += 1
        return t

    def node(self, kind, children, first, value=''):
        return Expr(kind, children, value, start=self.spans[first][0], end=self.spans[self.i-1][1])

    def parse(self):
        first = self.i
        if self.peek() == '=':
            self.take()
            node = self.node('continuation', [self.sum()], first)
        else:
            node = self.sum()
            if self.peek() == '=':
                self.take()
                node = self.node('eq', [node, self.sum()], first)
        if self.peek() is not None:
            raise LatexSyntaxError(f'Unexpected token {self.peek()!r}')
        return node

    def sum(self):
        first = self.i
        terms = [self.product()]
        while self.peek() in ('+', '-'):
            sign_pos = self.i
            sign = self.take()
            term = self.product()
            terms.append(self.node('neg', [term], sign_pos) if sign == '-' else term)
        return terms[0] if len(terms) == 1 else self.node('add', terms, first)

    def product(self):
        first = self.i
        terms = [self.unary()]
        while True:
            t = self.peek()
            if t in (r'\times', r'\cdot', '*'):
                self.take()
                terms.append(self.unary())
            elif t is not None and (t in ('(', '{', r'\frac') or t[0].isalnum()):
                terms.append(self.unary())
            else:
                break
        return terms[0] if len(terms) == 1 else self.node('mul', terms, first)

    def unary(self):
        first = self.i
        if self.peek() in ('-', '+'):
            op = self.take()
            node = self.unary()
            return self.node('neg', [node], first) if op == '-' else node
        base = self.atom()
        if self.peek() == '^':
            self.take()
            if self.peek() == '{':
                exponent = self.atom()
            else:
                epos = self.i
                t = self.take()
                if not re.fullmatch(r'[a-zA-Z]|\d', t):
                    raise LatexSyntaxError('Use braces around this exponent, e.g. ^{-1} or ^{12}.')
                exponent = self.node('atom', [], epos, t)
                exponent.wrap = True  # diagnostic specials must stay inside the script argument
            base = self.node('pow', [base, exponent], first)
        return base

    def atom(self):
        first = self.i
        t = self.take()
        if t in ('{', '('):
            node = self.sum()
            self.take('}' if t == '{' else ')')
            # Brace groups retain the interior span: do not insert specials
            # between \\frac and its required brace arguments.
            return node if t == '{' else self.node('paren', [node], first)
        if t == r'\frac':
            terms = []
            for _ in range(2):
                self.take('{')
                terms.append(self.sum())
                self.take('}')
            return self.node('frac', terms, first)
        if re.fullmatch(r'\d+(?:\.\d+)?|[a-zA-Z]', t):
            return self.node('atom', [], first, t)
        raise LatexSyntaxError(f'Expected a number, symbol or group, got {t!r}')


def parse_latex(text):
    return Parser(text).parse()


def _tagged_tex(text, root):
    """Zero-width DVI/SVG markers; no manual typesetting or extra math atoms."""
    events, nodes = {}, []
    def event(offset, phase, depth, order, value):
        events.setdefault(offset, []).append((phase, depth, order, value))
    def visit(node, depth, close_at=None):
        uid = f'ams{len(nodes)}'
        nodes.append((uid, node))
        if node.wrap:
            event(node.start, -1, depth, 0, '{')
            event(node.end, 0, -depth, 1, '}')
        event(node.start, 1, depth, 0, rf"\special{{dvisvgm:raw <g id='{uid}'>}}")
        event(node.end if close_at is None else close_at, 0, -depth, 0,
              r"\special{dvisvgm:raw </g>}")
        for i, child in enumerate(node.children):
            # A whatsit after \\right can detach its superscript. Close the
            # base's SVG group at the start of the script instead, inside its
            # braces, before the first exponent glyph is emitted.
            delayed = node.children[1].start if node.kind == 'pow' and i == 0 else None
            visit(child, depth + 1, delayed)
    visit(root, 0)
    result, previous = [], 0
    for offset in sorted(events):
        result.append(text[previous:offset])
        result.extend(e[3] for e in sorted(events[offset]))
        previous = offset
    result.append(text[previous:])
    return ''.join(result), nodes


def _svg_membership(svg_path):
    """Map emitted SVG drawing order to nested semantic group IDs."""
    memberships, groups = [], {}
    drawing_tags = {'use', 'path', 'rect', 'line', 'polygon', 'polyline', 'circle', 'ellipse'}
    def walk(element, active):
        tag = element.tag.rsplit('}', 1)[-1]
        if tag in ('defs', 'clipPath', 'mask', 'metadata', 'title', 'desc'):
            return
        uid = element.get('id', '')
        if uid.startswith('ams'):
            active = (*active, uid)
            groups.setdefault(uid, [])
        if tag in drawing_tags:
            index = len(memberships)
            memberships.append(active)
            for name in active:
                groups[name].append(index)
            return
        for child in element:
            walk(child, active)
    walk(ET.parse(svg_path).getroot(), ())
    return memberships, groups


def _render_native(text, root, font_size, color, tex_template=None):
    """Display the unmodified TeX render; the marked render is only a lookup."""
    options = dict(font_size=font_size, color=color)
    if tex_template is not None:
        options['tex_template'] = tex_template
    # SingleStringMathTex is MathTex's full-expression renderer, without
    # substring splitting; original spacing, delimiters and scripts are intact.
    row = mn.SingleStringMathTex(text, **options)
    tagged, nodes = _tagged_tex(text, root)
    probe = mn.SingleStringMathTex(tagged, **options)
    original_parts = [m for m in row.get_family() if m.has_points()]
    probe_parts = [m for m in probe.get_family() if m.has_points()]
    memberships, groups = _svg_membership(probe.file_name)
    if len(memberships) != len(probe_parts) or len(original_parts) != len(probe_parts):
        raise RuntimeError('SVG glyph mapping differs in this TeX/Manim version. '
                           'Please report the expression and your Manim version.')
    # Fail explicitly if markers ever change layout or glyph drawing order.
    # Never silently return an approximation of the requested TeX layout.
    probe.move_to(row.get_center())
    for a, b in zip(original_parts, probe_parts):
        if a.points.shape != b.points.shape or not np.allclose(a.points, b.points, atol=2e-5, rtol=0):
            raise RuntimeError('Diagnostic markers changed LaTeX geometry for: ' + text)
    for uid, node in nodes:
        indices = groups.get(uid, [])
        if not indices:
            raise RuntimeError(f'No SVG glyphs found for {text[node.start:node.end]!r}')
        node.mob = mn.VGroup(*(original_parts[i] for i in indices))
    # References share the real row glyphs, so arrange/scale/color propagate.
    for _, node in nodes:
        kids = [child.mob for child in node.children]
        if node.kind == 'pow':
            node.mob.base, node.mob.exponent = kids
        elif node.kind == 'paren':
            node.mob.inner = kids[0]
        elif node.kind == 'frac':
            node.mob.numerator, node.mob.denominator = kids
    row.expression = root
    row.semantic_parts = root.mob
    return row


def _bare(node):
    while node.kind == 'paren':
        node = node.children[0]
    return node


def _match(a, b, pairs):
    # A leading equality is punctuation, not part of the algebraic expression.
    # Leave it to the punctuation track so the arithmetic rules still apply.
    if a.kind == 'continuation' or b.kind == 'continuation':
        _match(a.children[0] if a.kind == 'continuation' else a,
               b.children[0] if b.kind == 'continuation' else b, pairs)
        return
    if a.key() == b.key():
        pairs.append((a, b))
        return
    # (a^b)^c -> a^(b*c): keep identities of all three operands.
    if a.kind == b.kind == 'pow':
        inner = _bare(a.children[0])
        exp = _bare(b.children[1])
        if (inner.kind == 'pow' and exp.kind == 'mul' and len(exp.children) == 2
                and inner.children[0].key() == b.children[0].key()
                and _bare(inner.children[1]).key() == _bare(exp.children[0]).key()
                and _bare(a.children[1]).key() == _bare(exp.children[1]).key()):
            _match(inner.children[0], b.children[0], pairs)
            _match(inner.children[1], exp.children[0], pairs)
            _match(a.children[1], exp.children[1], pairs)
            return
    # a^b * a^c -> a^(b+c): both bases travel into the same base.
    if a.kind == 'mul' and b.kind == 'pow':
        factors = [_bare(c) for c in a.children]
        exponent = _bare(b.children[1])
        if (all(c.kind == 'pow' for c in factors)
                and all(c.children[0].key() == b.children[0].key() for c in factors)
                and exponent.kind == 'add' and len(exponent.children) == len(factors)
                and all(c.children[1].key() == e.key()
                        for c, e in zip(factors, exponent.children))):
            for factor, term in zip(factors, exponent.children):
                _match(factor.children[0], b.children[0], pairs)
                _match(factor.children[1], term, pairs)
            return
    if a.kind == 'paren' or b.kind == 'paren':
        aa, bb = _bare(a), _bare(b)
        if aa.key() == bb.key() or aa.kind == bb.kind:
            _match(aa, bb, pairs)
            return
    if a.kind == b.kind and a.kind != 'atom' and len(a.children) == len(b.children):
        for ac, bc in zip(a.children, b.children):
            _match(ac, bc, pairs)
        return
    # Changed subexpression transforms as a whole: 4 -> (2^2), 2*(-1/2) -> -1.
    pairs.append((a, b))


def correspondence(source, target):
    pairs = []
    _match(source, target, pairs)
    return pairs


def _leaves(mob):
    return [m for m in mob.get_family() if m.has_points()]


class AutoMathSteps(mn.VGroup):
    """Parse LaTeX rows and animate structure-aware copies between them.

    .trees[i] exposes the parsed expression (kind, children, mob).
    .plan(i) reports semantic pairs for transition i -> i+1.
    Unknown syntax raises an error. Unrecognized changes morph a whole subtree.
    Rows use the original full-expression LaTeX layout. SVG markers are used
    only in a diagnostic render to identify semantic subexpressions.
    """
    def __init__(self, *latex_steps, color=mn.BLACK, font_size=48, tex_template=None, **kwargs):
        if len(latex_steps) == 1 and isinstance(latex_steps[0], (list, tuple)):
            latex_steps = tuple(latex_steps[0])
        if not latex_steps:
            raise ValueError('Provide at least one LaTeX expression.')
        self.latex_steps = tuple(latex_steps)
        self.trees = [parse_latex(s) for s in latex_steps]
        rows = [_render_native(text, tree, font_size, color, tex_template)
                for text, tree in zip(latex_steps, self.trees)]
        super().__init__(*rows, **kwargs)
        self.arrange(mn.DOWN, aligned_edge=mn.LEFT, buff=.3)

    def plan(self, index):
        return correspondence(self.trees[index], self.trees[index + 1])

    def play(self, scene, run_time=1.5, pause=.35, follow_camera=False):
        """Keep previous rows visible. MovingCameraScene is optional.

        With follow_camera=True, position/scale the group yourself; the camera
        follows each target row. Otherwise fit the whole group before play().
        """
        if follow_camera and not hasattr(scene.camera, 'frame'):
            raise TypeError('follow_camera=True requires MovingCameraScene.')
        scene.add(self[0])
        if pause:
            scene.wait(pause)
        for i in range(len(self.trees) - 1):
            source, target = self[i], self[i + 1]
            animations, temporary = [], []
            used_source, used_target = set(), set()
            for a, b in self.plan(i):
                src, dst = a.mob.copy(), b.mob.copy()
                temporary.extend((src, dst))
                animations.append(mn.ReplacementTransform(src, dst))
                used_source.update(id(m) for m in _leaves(a.mob))
                used_target.update(id(m) for m in _leaves(b.mob))
            # Match remaining punctuation in reading order.
            left = [m for m in _leaves(source) if id(m) not in used_source]
            right = [m for m in _leaves(target) if id(m) not in used_target]
            if left and right:
                src = mn.VGroup(*(m.copy() for m in left))
                dst = mn.VGroup(*(m.copy() for m in right))
                animations.append(mn.ReplacementTransform(src, dst))
                temporary.extend((src, dst))
            elif left:
                src = mn.VGroup(*(m.copy() for m in left))
                animations.append(mn.FadeOut(src, shift=target.get_center()-source.get_center()))
                temporary.append(src)
            elif right:
                dst = mn.VGroup(*(m.copy() for m in right))
                animations.append(mn.FadeIn(dst, shift=.12 * mn.DOWN))
                temporary.append(dst)
            if follow_camera:
                animations.append(scene.camera.frame.animate.set_y(target.get_center()[1]))
            scene.play(*animations, run_time=run_time)
            scene.remove(*temporary)
            scene.add(target)
            if pause:
                scene.wait(pause)
        return self


EXAMPLE_STEPS = (
    r'2^{\frac{3}{2}} \times 4^{-\frac{1}{2}}',
    r'2^{\frac{3}{2}} \times (2^2)^{-\frac{1}{2}}',
    r'2^{\frac{3}{2}} \times 2^{2 \times \left(-\frac{1}{2}\right)}',
    r'2^{\frac{3}{2}} \times 2^{-1}',
    r'2^{\frac{3}{2}-1}',
    r'2^{\frac{1}{2}}',
)


class AutoMathDemo(mn.MovingCameraScene):
    def construct(self):
        self.camera.background_color = mn.WHITE
        solution = AutoMathSteps(*EXAMPLE_STEPS, color=mn.BLACK)
        solution.arrange(mn.DOWN, aligned_edge=mn.LEFT, buff=.28)
        scale = min(1, (mn.config.frame_height-.8)/solution.height,
                    (mn.config.frame_width-1)/solution.width)
        solution.scale(scale).move_to(mn.ORIGIN)
        solution.play(self)
        self.wait(1)
