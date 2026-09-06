from manim import *


class HelloManim(Scene):
    def construct(self):
        styles = [
            ("Write", Write),
            ("AddTextLetterByLetter", AddTextLetterByLetter),
            ("FadeIn", lambda text: FadeIn(text, shift=UP)),
            ("ShowIncreasingSubsets", ShowIncreasingSubsets),
            ("DrawBorderThenFill", DrawBorderThenFill),
            ("FadeIn from below", lambda text: FadeIn(text, shift=DOWN)),
            ("GrowFromCenter", GrowFromCenter),
            ("SpinInFromNothing", SpinInFromNothing),
            ("FadeInFromPoint", lambda text: FadeInFromPoint(text, point=ORIGIN)),
        ]

        for style_name, animation in styles:
            label = Text(style_name, font_size=28, color=GRAY_B).to_edge(UP)
            text = Text("Hello, Manim!", font_size=56, color=YELLOW)

            self.play(FadeIn(label))
            self.play(animation(text), run_time=2)
            self.wait(0.5)
            self.play(FadeOut(text), FadeOut(label))
