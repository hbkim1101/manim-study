"""프로젝트 루트에서 python -m unittest discover -s tests -p test_auto_latex.py"""
import unittest
from module.auto_latex import parse_latex, match_latex, numeric, LatexSyntaxError

STEPS = [
    r'2^{\frac{3}{2}}\times4^{-\frac{1}{2}}',
    r'=2^{\frac{3}{2}}\times(2^2)^{-\frac{1}{2}}',
    r'=2^{\frac{3}{2}}\times2^{2\times(-\frac{1}{2})}',
    r'=2^{\frac{3}{2}}\times2^{-1}',
    r'=2^{\frac{3}{2}-1}',
    r'=2^{\frac{1}{2}}',
]


class AutoMappingTests(unittest.TestCase):
    def transition(self, i):
        a,b = parse_latex(STEPS[i]), parse_latex(STEPS[i+1])
        links,report = match_latex(a,b)
        return a,b,links,report

    def test_core_steps_no_heuristics_and_no_mutation(self):
        for i in range(5):
            a,b,links,report = self.transition(i)
            self.assertFalse(any(r['reason']=='heuristic' for r in report))
            self.assertEqual(b[0].key(),parse_latex(STEPS[i+1])[0].key())
            self.assertEqual(a[0].key(),parse_latex(STEPS[i])[0].key())
            self.assertEqual((links,report),match_latex(a,b))

    def test_four_splits_into_two_twos(self):
        a,b,links,_=self.transition(0)
        four=next(u.index for u in a[1] if u.tex=='4')
        target=[u for u in b[1] if u.tex=='2' and u.path[:2]==(3,'base')]
        self.assertEqual(len(target),2)
        self.assertTrue(all(four in links[u.index] for u in target))

    def test_moved_exponent_keeps_its_own_two(self):
        a,b,links,_=self.transition(1)
        base=next(u for u in b[1] if u.path==(3,'base','value'))
        exponent=next(u for u in b[1] if u.path==(3,'exponent',0,'value'))
        self.assertIn('base',a[1][links[base.index][0]].path)
        self.assertEqual(a[1][links[exponent.index][0]].path[-2],'exponent')
        self.assertNotEqual(links[base.index],links[exponent.index])

    def test_calculation_does_not_merge_into_base(self):
        a,b,links,_=self.transition(2)
        base=next(u for u in b[1] if u.path==(3,'base','value'))
        self.assertEqual(len(links[base.index]),1)
        self.assertEqual(a[1][links[base.index][0]].path,base.path)
        result=next(u for u in b[1] if u.path==(3,'exponent',1,'value'))
        self.assertGreater(len(links[result.index]),1)
        self.assertTrue(all('exponent' in a[1][i].path for i in links[result.index]))

    def test_two_bases_merge(self):
        a,b,links,_=self.transition(3)
        base=next(u for u in b[1] if u.path==(1,'base','value'))
        self.assertEqual(len(links[base.index]),2)
        self.assertTrue(all(a[1][i].tex=='2' and a[1][i].path[-2]=='base' for i in links[base.index]))

    def test_fraction_calculation(self):
        a,b,links,_=self.transition(4)
        numerator=next(u for u in b[1] if u.path==(1,'exponent','numerator','value'))
        self.assertEqual({a[1][i].tex for i in links[numerator.index]},{'3','-','1'})

    def test_numeric(self):
        for expression,value in [('2+3',5),('2-3*4',-10),(r'6\cdot2^2-1',23),(r'\frac{9}{3}',3),('2*-3',-6)]:
            self.assertEqual(numeric(parse_latex(expression)[0]),value)
        self.assertIsNone(numeric(parse_latex('x+1')[0]))
        self.assertIsNone(numeric(parse_latex(r'\frac{1}{0}')[0]))

    def test_manual_and_new_target_are_preserved(self):
        a,b=parse_latex('x+y'),parse_latex('y+x')
        links,report=match_latex(a,b,{0:[2],2:[0]})
        self.assertEqual(links[0],[2]);self.assertEqual(links[2],[0])
        self.assertEqual(b[0].key(),parse_latex('y+x')[0].key())
        with self.assertRaises(ValueError):match_latex(a,b,{900:[0]})

    def test_parser_rejects_unsupported_and_malformed(self):
        for expression in ['',r'\begin{matrix}1\end{matrix}',r'\text{hello}',r'\frac{1}',r'x^{2',r'x^^2',r'\left[2\right]',r'$x$']:
            with self.subTest(expression=expression),self.assertRaises(LatexSyntaxError):parse_latex(expression)
        self.assertEqual(parse_latex(r'\frac12')[0].key(),parse_latex(r'\frac{1}{2}')[0].key())
        root,_=parse_latex('x^12')
        self.assertEqual(root.children[0].children[1].text,'1')
        self.assertEqual(root.children[1].text,'2')
        self.assertEqual(parse_latex(r'\left(2^2\right)')[0].key(),parse_latex('(2^2)')[0].key())
        root,units=parse_latex(r'f\mid_{x\geq0}')
        self.assertEqual([unit.tex for unit in units],['f',r'\mid','x',r'\geq','0'])
        self.assertEqual(root.children[1].text,'_')

if __name__=='__main__':unittest.main()
