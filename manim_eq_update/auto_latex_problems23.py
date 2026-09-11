"""PDF 없이 실행: python -m manim -ql auto_latex_problems23.py Problem2 Problem3"""
from manim import config
from module.mobjects import ProblemScene
from module.simple_solution_flow import SolutionFlow

config.notify_outdated_version = False

PROBLEM2 = ['f(x)=2x^3-x-4', '\\Rightarrow f^{\\prime}(x)=6x^2-1', '\\lim_{x\\to2}\\frac{f(x)-f(2)}{x-2}', '=f^{\\prime}(2)', '=6x^2-1', '=6\\cdot2^2-1', '=24-1', '=23']
MODES2 = [False, False, False, False, True, True, True]

class Problem2(ProblemScene):
    def construct(self):
        flow = SolutionFlow(self, run_time=0.8, pause=0.3)
        flow.play_latex(*PROBLEM2, same_line=MODES2, strict=True)
        flow.finish()

PROBLEM3 = ['a_{10}-a_7=9', 'a_{10}-a_7=3d=9', 'd=\\frac{9}{3}', 'd=3', 'a_7', 'a_7=a_2+5d', 'a_7=2+5\\cdot3', 'a_7=17']
MODES3 = [True, False, True, False, True, False, True]

class Problem3(ProblemScene):
    def construct(self):
        flow = SolutionFlow(self, run_time=0.8, pause=0.3)
        flow.play_latex(*PROBLEM3, same_line=MODES3, strict=True)
        flow.finish()
