"""python -m manim -ql tests/test_problems23_render.py Problem2Tests Problem3Tests"""
import hashlib
import numpy as np
from manim import config, Wait
from module.mobjects import ProblemScene, _ordered_parts, _dynamic_family
from module.simple_solution_flow import SolutionFlow, _SnapshotTransition
from module.auto_latex import parse_latex, render_latex
from auto_latex_problems23 import PROBLEM2, PROBLEM3, MODES2, MODES3
config.notify_outdated_version=False


def state(eq):
    return eq.get_tex_string(), tuple((str(p.id),str(p.source_id),str(p.target_id),
        hashlib.sha256(p.get_all_points().tobytes()).hexdigest()) for p in _dynamic_family(eq))


def check(scene, expressions, modes, parents, final, external_step):
    limit, _ = render_latex(parse_latex(r'\lim_{x\to2}'))
    symbol, below = limit[0].base, limit[0].subscript
    assert abs(symbol.get_center()[0]-below.get_center()[0]) < .01
    assert below.get_top()[1] < symbol.get_bottom()[1]
    flow=SolutionFlow(scene,pause=.3,run_time=.8,camera_run_time=.3)
    eqs=flow.latex_steps(*expressions,same_line=modes,strict=True)
    for i,j in enumerate(parents,1):
        step=flow.steps[id(eqs[i])]
        assert step.parent is eqs[j]
        available={p.id for p in _ordered_parts(eqs[j])}
        available.update(p.id for e in step.external for p in _ordered_parts(e))
        assert all(set(p._change_source_ids)<=available for p in _ordered_parts(eqs[i]))
    assert flow.steps[id(eqs[external_step])].external
    flow.stack(*eqs)
    before=[state(eq) for eq in eqs]
    original_play = scene.play
    branch_checks = []
    def checked_play(*animations, **kwargs):
        transitions = [a for a in animations if isinstance(a, _SnapshotTransition)]
        camera_return = (not transitions and flow.current is not None
                         and any(not isinstance(a, Wait) for a in animations))
        if camera_return:
            assert flow.current is eqs[3] and parents[3] == 1
            assert np.allclose(scene.camera.frame.get_center(), eqs[3].get_center())
        if transitions:
            animation = transitions[0]
            assert len(animations) == 2, 'camera must move alongside equation'
            # 문제 2의 5번째 식: 카메라가 play로 출발식에 도착한 상태.
            if parents[3]==1 and flow.current is eqs[3] and animation.source_display is flow.displays[id(eqs[1])][0]:
                assert np.allclose(scene.camera.frame.get_center(), animation.source_display.get_center())
                branch_checks.append(True)
        result = original_play(*animations, **kwargs)
        if camera_return:
            assert np.allclose(scene.camera.frame.get_center(), eqs[1].get_center())
        if transitions:
            assert np.allclose(scene.camera.frame.get_center(), transitions[0].target_display.get_center())
        return result
    scene.play = checked_play
    try:
        flow.play_linear()
    finally:
        scene.play = original_play
    if parents[3]==1: assert branch_checks
    assert before==[state(eq) for eq in eqs], 'original mutation'
    assert final in eqs[-1].get_tex_string()
    assert flow.displays[id(eqs[-1])][0] in scene.mobjects
    flow.finish()
    print('PASS',scene.__class__.__name__,'parents, external provenance, replay, original preservation, final',final)

class Problem2Tests(ProblemScene):
    def construct(self):
        check(self,PROBLEM2,MODES2,[0,1,2,1,4,5,6],'23',5)

class Problem3Tests(ProblemScene):
    def construct(self):
        check(self,PROBLEM3,MODES3,list(range(7)),'17',6)
