import hashlib
import numpy as np
from manim import *
from reactive_manim import *
from module.mobjects import *
from module.mobjects import _dynamic_family, _ordered_parts
from module.simple_solution_flow import SolutionFlow

config.notify_outdated_version = False


def snapshot(eq):
    return (eq.get_tex_string(), tuple(sorted(
        (str(p.id), str(p.source_id), str(p.target_id),
         id(p.parent) if p.parent else None,
         hashlib.sha256(p.get_all_points().tobytes()).hexdigest())
        for p in _dynamic_family(eq))))


class SnapshotTests(ProblemScene):
    def construct(self):
        MathTex.set_default(font_size=36, color=BLACK)
        flow = SolutionFlow(self, run_time=.2, pause=0, camera_run_time=.1)
        eq1 = MathTex(Term(2, 3), '+', 4)
        before = snapshot(eq1)
        eq1_1 = flow.change_at(eq1, '0.exponent', 2)
        branch = flow.change_at(eq1, '0.exponent', 5)
        assert snapshot(eq1) == before
        assert eq1_1[0].exponent.get_tex_string() == '2'
        assert branch[0].exponent.get_tex_string() == '5'
        eq2 = flow.evolve(eq1_1, build=lambda q: MathTex(
            '=', change([q[0], q[2]], 8)))
        assert snapshot(eq1) == before
        flat = MathTex(2, 3, 4)
        flat_before = snapshot(flat)
        merged = change(list(flat), Fraction(1, 2))
        split = change(flat[0], Paren(Term(2, 2)))
        assert snapshot(flat) == flat_before
        assert len(set(sid for p in _ordered_parts(merged)
                       for sid in p._change_source_ids)) == 3
        assert len(_ordered_parts(split)) >= 3
        inserted = flow.append(eq1, "=", 8)
        assert inserted[-1].get_color() == eq1.get_color()
        assert inserted[-2].get_color() == eq1.get_color()
        safe = equation(eq1[0], eq1[2])
        assert snapshot(eq1) == before
        assert safe[0] is not eq1[0]
        for operation in [
            lambda: change([], 2),
            lambda: flow.change_at(eq1, '99.base', 2),
            lambda: flow.evolve(eq1, {'0': 2, '0.base': 3}),
            lambda: flow.collapse_from(eq1, 8, 2),
            lambda: flow.evolve(eq1, inserts=[(99, 'x')]),
        ]:
            try: operation()
            except (ValueError, IndexError): pass
            else: raise AssertionError('invalid edit accepted')
        assert snapshot(eq1) == before
        flow.stack(eq1, eq1_1, eq2)
        assert np.allclose(eq1.get_corner(UL), eq1_1.get_corner(UL))
        saved = [snapshot(q) for q in [eq1, eq1_1, eq2]]
        flow.play_linear()
        assert saved == [snapshot(q) for q in [eq1, eq1_1, eq2]]
        assert flow.displays[id(eq1)][0] not in self.mobjects
        assert flow.displays[id(eq1_1)][0] in self.mobjects
        assert flow.displays[id(eq2)][0] in self.mobjects
        print('PASS: preservation, branches, N/M links, errors, same-line layout, playback')


class LegacyTests(ProblemScene):
    def construct(self):
        MathTex.set_default(font_size=36, color=BLACK)
        source = MathTex('2', '+', '3')
        before = snapshot(source)
        target = equation(change([source[0], source[2]], 5)).shift(DOWN)
        assert snapshot(source) == before
        self.add(source)
        self.play(TransformInStages.from_copy(source, target), run_time=.2)
        assert source[0].target_id is None
        self.wait(.1)
        print('PASS: legacy from_copy N -> 1')


class LegacyProgressTests(ProblemScene):
    def construct(self):
        eq = MathTex(2, '+', 3)
        self.add(eq)
        eq.terms = [change([eq[0], eq[2]], 5)]
        self.play(TransformInStages.progress(eq), run_time=.2)
        self.wait(.1)
        print('PASS: legacy progress N -> 1')


class ConvenienceTests(ProblemScene):
    def construct(self):
        flow = SolutionFlow(self, run_time=.2, pause=0, camera_run_time=.1)
        eq = MathTex('=', Term(2, Fraction(3, 2)), r'\times',
                     Term(Paren(Term(2, 2)), ['-', Fraction(1, 2)]))
        eq[1].base.set_color(RED)
        source = snapshot(eq)
        expanded = flow.flatten_power(eq)
        assert snapshot(eq) == source
        assert isinstance(expanded[3], Term)
        assert expanded[3].base.id == eq[3].base.inner.base.id
        assert expanded[3].exponent[0].id == eq[3].base.inner.exponent.id
        assert expanded[3].exponent[2].inner[1].id == eq[3].exponent[1].id
        assert expanded[1].base.get_color() == RED
        assert expanded[3].exponent[1].get_color() == eq[3].get_color()
        exp_before = snapshot(expanded)
        evaluated = flow.set_exponent(expanded, 3, -1)
        assert snapshot(expanded) == exp_before
        val_before = snapshot(evaluated)
        combined = flow.combine_powers(evaluated)
        assert snapshot(evaluated) == val_before
        assert len(combined) == 2
        assert combined[1].exponent[1].get_tex_string() == '-1'
        linked = {sid for p in _ordered_parts(combined[1].base)
                  for sid in p._change_source_ids}
        assert linked == {evaluated[1].base.id, evaluated[3].base.id}
        assert combined[1].base.get_color() == RED
        final = flow.set_exponent(combined, 1, Fraction(1, 2))
        assert isinstance(final[1].exponent, Fraction)
        changed_base = flow.set_base(eq, 1, 3)
        assert changed_base[1].base.get_tex_string() == '3'
        assert snapshot(eq) == source

        fraction_eq = MathTex('=', Fraction(2, 3))
        saved = snapshot(fraction_eq)
        flipped = flow.rewrite(fraction_eq, 1,
                               lambda p: Fraction(p.denominator, p.numerator))
        assert snapshot(fraction_eq) == saved
        assert flipped[1].numerator.id == fraction_eq[1].denominator.id
        assert flipped[1].denominator.id == fraction_eq[1].numerator.id
        scalar = flow.rewrite(fraction_eq, 1, lambda p: 7)
        assert scalar[1].get_tex_string() == '7'
        positive = MathTex(Term(2, 3), r'\cdot', Term(2, 4))
        plus = flow.combine_powers(positive)
        assert plus[0].exponent[1].get_tex_string() == '+'

        ambiguous = MathTex(Term(Paren(Term(2, 2)), 3), '+',
                            Term(Paren(Term(3, 2)), 4))
        explicit = flow.flatten_power(ambiguous, 2)
        assert explicit[2].base.get_tex_string() == '3'
        plus_eq = MathTex(Term(2, 3), '+', Term(2, 4))
        different = MathTex(Term(2, 3), r'\times', Term(3, 4))
        nested = MathTex(Fraction(Term(Paren(Term(2, 2)), 3), 7))
        nested_new = flow.flatten_power(nested, '0.numerator')
        assert nested_new[0].numerator.base.get_tex_string() == '2'
        for operation in [lambda: flow.flatten_power(ambiguous),
                          lambda: flow.flatten_power(plus_eq),
                          lambda: flow.combine_powers(plus_eq, 0, 2),
                          lambda: flow.combine_powers(different),
                          lambda: flow.combine_powers(positive, 0),
                          lambda: flow.rewrite(eq, 1, lambda p: None)]:
            try: operation()
            except ValueError: pass
            else: raise AssertionError('invalid convenience operation accepted')
        assert snapshot(eq) == source
        assert snapshot(fraction_eq) == saved

        flow.stack(eq, expanded, evaluated, combined, final)
        states = [snapshot(q) for q in flow.sequence]
        flow.play_linear()
        assert [snapshot(q) for q in flow.sequence] == states
        print('PASS: convenience helpers, original preservation, color, source IDs, ambiguity, rendering')
