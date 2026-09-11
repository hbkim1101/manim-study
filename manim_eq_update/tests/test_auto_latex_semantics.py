import unittest
from module.auto_latex import parse_latex, match_latex, plan_latex
from auto_latex_problems23 import PROBLEM2, PROBLEM3, MODES2, MODES3


def plan(seq, modes, **kwargs):
    return plan_latex(list(map(parse_latex, seq)), modes, [None]*(len(seq)-1), **kwargs)

class SemanticMappingTests(unittest.TestCase):
    def test_problem2_sources_and_external_argument(self):
        plans = plan(PROBLEM2, MODES2)
        self.assertEqual([p['source'] for p in plans], [0,1,2,1,4,5,6])
        self.assertEqual(plans[4]['external'], {3:(3,[4])})
        self.assertFalse(any(r['reason']=='heuristic' for p in plans for r in p['report']))
        target = parse_latex(PROBLEM2[5])[1]
        exponent = next(u.index for u in target if 'exponent' in u.path)
        self.assertNotIn(exponent, plans[4]['external'])

    def test_power_calculation_prefers_previous_step(self):
        from test_auto_latex import STEPS
        self.assertEqual([p['source'] for p in plan(STEPS, [False]*5)], list(range(5)))

    def test_derivative_provenance(self):
        a,b=map(parse_latex,PROBLEM2[:2]);links,report=match_latex(a,b)
        pairs={r['reason']:[a[1][i].tex for i in r['sources']] for r in report if r['reason'].startswith('derivative')}
        self.assertEqual(pairs['derivative-coefficient'], ['2','3'])
        self.assertEqual(pairs['derivative-exponent'], ['3'])
        self.assertEqual(pairs['derivative-constant'], ['x'])
        self.assertFalse(any(a[1][i].tex=='4' for r in report for i in r['sources']))

    def test_derivative_variant_and_invalid_result(self):
        for result,expected in [('12t^3-2', True),('11t^3-2',False)]:
            _,report=match_latex(parse_latex('g(t)=3t^4-2t+7'),parse_latex(r'g^{\prime}(t)='+result))
            self.assertEqual(any(r['reason']=='derivative-coefficient' for r in report),expected)

    def test_problem3_subscript_and_context(self):
        plans=plan(PROBLEM3,MODES3)
        self.assertEqual([p['source'] for p in plans], list(range(7)))
        self.assertTrue(all(r['reason']=='new-statement' for r in plans[3]['report']))
        self.assertEqual(plans[5]['external'], {})
        a=parse_latex(PROBLEM3[5])[1]
        row=next(r for r in plans[5]['report'] if r['tex']=='2')
        self.assertCountEqual([a[i].tex for i in row['sources']], ['a','2'])
        self.assertFalse(any(r['reason']=='heuristic' for p in plans for r in p['report']))

    def test_problem3_fraction_keeps_coefficient_and_rhs_sources(self):
        source, target = map(parse_latex, PROBLEM3[1:3])
        _, report = match_latex(source, target)
        numerator = next(r for r in report if r['path'] == '2.numerator.value')
        denominator = next(r for r in report if r['path'] == '2.denominator.value')
        self.assertEqual([source[1][i].tex for i in numerator['sources']], ['9'])
        self.assertEqual([source[1][i].tex for i in denominator['sources']], ['3'])
        result = next(r for r in report if r['tex'] == '3')
        self.assertEqual(result['reason'], 'calculation-result')

        plans = plan(PROBLEM3, MODES3)
        self.assertEqual(plans[2]['external'], {})

        final = plans[5]
        self.assertEqual(final['external'], {})
        replacement = next(r for r in final['report'] if r['tex'] == '3')
        self.assertEqual(replacement['reason'], 'substitution')
        self.assertEqual(replacement['source_step'], 5)

    def test_context_does_not_borrow_wrong_value(self):
        seq=[r'd=4',r'a_7=a_2+5d',r'a_7=2+5\cdot3']
        plans=plan(seq,[False,False],sources=[0,1])
        self.assertFalse(plans[-1]['external'])

    def test_unavailable_source_rejected(self):
        with self.assertRaises(ValueError):plan(['x','y','z'],[True,False],sources=[0,0])

    def test_history_can_be_disabled_or_overridden(self):
        plans=plan(PROBLEM2,MODES2,use_history=False)
        self.assertEqual([p['source'] for p in plans],list(range(7)))
        plans=plan(PROBLEM2,MODES2,sources=[0,1,2,1,4,5,6])
        self.assertEqual(plans[3]['source'],1)

if __name__=='__main__':unittest.main()
