"""프로젝트 루트에서 python -m manim -ql auto_latex_demo.py AutoLatexDemo"""
from manim import *
from reactive_manim import *
from module.mobjects import *
from module.simple_solution_flow import SolutionFlow

config.notify_outdated_version = False


class AutoLatexDemo(ProblemScene):
    def construct(self):
        flow = SolutionFlow(self)
        flow.play_latex(
            r'2^{\frac{3}{2}} \times 4^{-\frac{1}{2}}',
            r'= 2^{\frac{3}{2}} \times (2^2)^{-\frac{1}{2}}',
            r'= 2^{\frac{3}{2}} \times 2^{2\times(-\frac{1}{2})}',
            r'= 2^{\frac{3}{2}} \times 2^{-1}',
            r'= 2^{\frac{3}{2}-1}',
            r'= 2^{\frac{1}{2}}',
        )
        flow.finish()
