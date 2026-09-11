"""python -m manim -ql tests/test_auto_latex_render.py AutoLatexTests"""
import hashlib
from manim import *
from reactive_manim import *
from module.mobjects import *
from module.mobjects import _ordered_parts, _dynamic_family
from module.simple_solution_flow import SolutionFlow
from module.auto_latex import parse_latex, render_latex

config.notify_outdated_version=False
STEPS = [
    r'2^{\frac{3}{2}}\times4^{-\frac{1}{2}}',
    r'=2^{\frac{3}{2}}\times(2^2)^{-\frac{1}{2}}',
    r'=2^{\frac{3}{2}}\times2^{2\times(-\frac{1}{2})}',
    r'=2^{\frac{3}{2}}\times2^{-1}',
    r'=2^{\frac{3}{2}-1}',
    r'=2^{\frac{1}{2}}',
]


def state(eq):
    return eq.get_tex_string(), tuple(sorted((str(p.id),str(p.source_id),str(p.target_id),
        hashlib.sha256(p.get_all_points().tobytes()).hexdigest()) for p in _dynamic_family(eq)))


class AutoLatexTests(ProblemScene):
    def construct(self):
        flow=SolutionFlow(self,pause=0,run_time=.25,camera_run_time=.1)
        eqs=flow.latex_steps(*STEPS,strict=True)
        for source,target in zip(eqs,eqs[1:]):
            source_ids={p.id for p in _ordered_parts(source)}
            self_links={sid for p in _ordered_parts(target) for sid in p._change_source_ids}
            assert self_links <= source_ids
            assert not any(r['reason']=='heuristic' for r in flow.mapping_report(target))
        report=flow.mapping_report(eqs[-1]);report.clear()
        assert flow.mapping_report(eqs[-1])
        for text in [r'\sqrt{x^2+1}',r'\sqrt[3]{8}',r'a_{10}-a_7',r'f^{\prime}(x)',r'\lim_{x\to2}\frac{x^2-4}{x-2}']:
            eq,binding=render_latex(parse_latex(text))
            ids=[p.id for parts in binding.values() for p in parts]
            assert len(ids)==len(set(ids))
            assert set(ids)=={p.id for p in _ordered_parts(eq)}
        try:flow.latex_steps('x','y',strict=True)
        except ValueError:pass
        else:raise AssertionError('strict accepted heuristic')
        manual=flow.latex_steps('x','y',links=[{0:[0]}],strict=True)
        assert flow.mapping_report(manual[1])[0]['reason']=='manual'
        assert manual[1].get_tex_string()=='y'
        flow.stack(*eqs)
        before=[state(eq) for eq in eqs]
        flow.play_linear()
        assert before==[state(eq) for eq in eqs]
        flow.finish(.3)
        # 같은 자리 수정과 다음 줄 복사를 섞어도 원본 수식은 유지된다.
        mixed=flow.latex_steps('2+3','5','5+1','6',same_line=[True,False,True])
        flow.stack(*mixed)
        assert np.allclose(mixed[0].get_corner(UL),mixed[1].get_corner(UL))
        assert np.allclose(mixed[2].get_corner(UL),mixed[3].get_corner(UL))
        before=[state(eq) for eq in mixed]
        flow.play_linear()
        assert before==[state(eq) for eq in mixed]
        flow.finish(.3)
        print('PASS: automatic LaTeX rendering, exact target, bindings, original preservation, mixed placement, manual overrides')
