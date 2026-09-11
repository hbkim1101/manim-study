"""LaTeX 구조 파싱 + 결정적 단계 매핑. 파서는 Manim 없이도 검사할 수 있다.

입력된 다음 식을 수정/계산하지 않는다. 계산 가능한 유리수 부분식의 동치성은
매핑에만 사용하며, 휴리스틱 연결은 report에서 구분한다.
"""
from dataclasses import dataclass, field
from fractions import Fraction as Rational
import re


@dataclass
class Node:
    kind: str
    text: str = ''
    children: list = field(default_factory=list)
    path: tuple = ()
    units: list = field(default_factory=list)
    own: list = field(default_factory=list)

    def key(self):
        if self.kind == 'seq' and len(self.children) == 1:
            return self.children[0].key()
        return (self.kind, self.text, tuple(c.key() for c in self.children))


@dataclass
class Unit:
    index: int
    tex: str
    path: tuple


SYMBOLS = set(r'''\times \cdot \div \pm \mp \le \leq \ge \geq \ne \neq
\approx \equiv \to \rightarrow \Rightarrow \Longrightarrow \infty
\alpha \beta \gamma \delta \epsilon \theta \lambda \mu \nu \pi \rho
\sigma \tau \phi \chi \psi \omega \Delta \Sigma \Omega \Gamma
\sin \cos \tan \log \ln \exp \lim \sum \prod \int \prime \partial \nabla
\in \notin \subset \cup \cap \forall \exists \mid \ldots \cdots'''.split())
SPACING = {r'\,', r'\;', r'\:', r'\!', r'\quad', r'\qquad', '\\ '}
TOKEN = re.compile(r'\\[a-zA-Z]+|\\.|\d+(?:\.\d+)?|[^\s]')


class LatexSyntaxError(ValueError):
    pass


class Parser:
    def __init__(self, text):
        if not isinstance(text, str) or not text.strip():
            raise LatexSyntaxError('비어 있지 않은 LaTeX 문자열이 필요합니다.')
        self.tokens = TOKEN.findall(text)
        self.i = 0

    def peek(self):
        return self.tokens[self.i] if self.i < len(self.tokens) else None

    def take(self):
        token = self.peek()
        if token is None:
            raise LatexSyntaxError('식이 예상보다 일찍 끝났습니다.')
        self.i += 1
        return token

    def sequence(self, end=None):
        nodes = []
        while self.peek() is not None and self.peek() != end:
            token = self.peek()
            if token in SPACING:
                self.take(); continue
            if token in ('}', ')', ']'):
                raise LatexSyntaxError(f'짝이 맞지 않는 닫는 기호: {token}')
            if token == r'\right':
                self.take()
                if end != ')' or self.peek() != ')':
                    raise LatexSyntaxError(r'현재 \left/\right는 둥근 괄호만 지원합니다.')
                break
            node = self.atom()
            scripts = {}
            while self.peek() in ('^', '_', "'"):
                symbol = self.take()
                if symbol == "'":
                    if '^' in scripts:
                        raise LatexSyntaxError('지수가 중복되었습니다.')
                    count = 1
                    while self.peek() == "'": self.take(); count += 1
                    scripts['^'] = Node('atom', r'\prime' * count)
                    continue
                if symbol in scripts:
                    raise LatexSyntaxError('같은 종류의 첨자가 중복되었습니다.')
                scripts[symbol] = self.argument(script=True)
            if scripts:
                node = Node('script', ''.join(k for k in ('^', '_') if k in scripts),
                            [node] + [scripts[k] for k in ('^', '_') if k in scripts])
            nodes.append(node)
        if end is not None:
            if self.take() != end:
                raise LatexSyntaxError(f'{end}로 닫아야 합니다.')
        return Node('seq', children=nodes)

    def argument(self, script=False):
        if self.peek() == '{':
            self.take()
            node = self.sequence('}')
            if not node.children:
                raise LatexSyntaxError('빈 그룹은 지원하지 않습니다.')
            return node.children[0] if len(node.children) == 1 else node
        # TeX의 ^12는 ^{1}2이다. 숫자 토큰 전체를 첨자로 삼지 않는다.
        token = self.peek()
        if script and token and token[0].isdigit() and len(token) > 1:
            self.tokens[self.i:self.i + 1] = [token[0], token[1:]]
        return self.atom()

    def atom(self):
        t = self.take()
        if t == '{':
            node = self.sequence('}')
            if not node.children: raise LatexSyntaxError('빈 그룹은 지원하지 않습니다.')
            return node.children[0] if len(node.children) == 1 else node
        if t == r'\left':
            if self.take() != '(':
                raise LatexSyntaxError(r'현재 \left/\right는 둥근 괄호만 지원합니다.')
            return Node('paren', children=[self.sequence(')')])
        if t == '(':
            return Node('paren', children=[self.sequence(')')])
        if t in (r'\frac', r'\dfrac', r'\tfrac'):
            return Node('frac', children=[self.argument(script=True), self.argument(script=True)])
        if t == r'\sqrt':
            index = None
            if self.peek() == '[':
                self.take(); index = self.sequence(']')
            body = self.argument(script=True)
            return Node('root', children=[body] + ([index] if index else []))
        if t in ('^', '_', '}', ')', '[', ']', '&', '$'):
            raise LatexSyntaxError(f'이 위치의 {t!r}는 지원하지 않습니다. 수학 모드 구분자 없이 입력하세요.')
        if t.startswith('\\') and t not in SYMBOLS:
            raise LatexSyntaxError(f'아직 지원하지 않는 LaTeX 명령: {t}. 기존 구조 API로 작성하세요.')
        return Node('atom', t)


def parse_latex(text):
    parser = Parser(text)
    root = parser.sequence()
    if not root.children: raise LatexSyntaxError('표시할 식이 없습니다.')
    units = []

    def add(node, text, suffix):
        idx = len(units)
        units.append(Unit(idx, text, node.path + (suffix,)))
        node.own.append(idx)
        return idx

    def visit(node, path=()):
        node.path = path
        if node.kind == 'atom': add(node, node.text, 'value')
        if node.kind == 'paren': add(node, '(', 'left')
        names = {'frac': ['numerator', 'denominator'], 'paren': ['inner'],
                 'root': ['radicand', 'index'],
                 'script': ['base'] + [('exponent' if s == '^' else 'subscript') for s in node.text]}
        for i, child in enumerate(node.children):
            visit(child, path + (names.get(node.kind, list(range(len(node.children))))[i],))
        if node.kind == 'frac': add(node, r'\fractionbar', 'bar')
        if node.kind == 'root': add(node, r'\sqrt', 'radical')
        if node.kind == 'paren': add(node, ')', 'right')
        node.units = sorted(node.own + [i for c in node.children for i in c.units])
    visit(root)
    return root, units


def walk(root):
    yield root
    for child in root.children: yield from walk(child)


def numeric(node):
    """정확한 유리수만 계산. eval이나 문자열 코드 실행을 사용하지 않는다."""
    try:
        if node.kind == 'atom':
            return Rational(node.text) if re.fullmatch(r'\d+(?:\.\d+)?', node.text) else None
        if node.kind == 'paren': return numeric(node.children[0])
        if node.kind == 'frac':
            a, b = map(numeric, node.children)
            return a / b if a is not None and b not in (None, 0) else None
        if node.kind == 'script' and node.text == '^':
            a, b = map(numeric, node.children)
            if a is None or b is None or (a == 0 and b <= 0) or abs(b) > 100 or b.denominator > 16: return None
            if b.denominator == 1: return a ** int(b)
            if a < 0: return None
            def exact_root(n, degree):
                if n > 10**18: return None
                guess = round(n ** (1 / degree))
                return next((x for x in range(max(0, guess-1), guess+2) if x**degree == n), None)
            top, bottom = exact_root(a.numerator, b.denominator), exact_root(a.denominator, b.denominator)
            return Rational(top, bottom) ** b.numerator if top is not None and bottom else None
        if node.kind == 'seq':
            items = node.children
            total, product, sign, pending, want_value = Rational(0), None, 1, '*', True
            for item in items:
                token = item.text if item.kind == 'atom' else ''
                if token in ('+', '-'):
                    if want_value:
                        if token == '-': sign *= -1
                    else:
                        total += product
                        product, sign, pending, want_value = None, (-1 if token == '-' else 1), '*', True
                elif token in (r'\times', r'\cdot', '*', '/', r'\div'):
                    if want_value: return None
                    pending, want_value = ('/' if token in ('/', r'\div') else '*'), True
                else:
                    value = numeric(item)
                    if value is None: return None
                    value *= sign; sign = 1
                    if product is None: product = value
                    elif pending == '/': product /= value
                    else: product *= value
                    pending, want_value = '*', False
            return total + product if product is not None and not want_value else None
    except (ZeroDivisionError, ValueError, OverflowError):
        return None
    return None


def role(path):
    return tuple(x for x in path if isinstance(x, str) and x not in ('inner', 'value'))


def distance(a, b):
    ar, br = role(a.path), role(b.path)
    return (0 if ar == br else 2 if ar[-1:] == br[-1:] else 5) + abs(a.index-b.index)*.02


def _atom(node, text=None):
    return node.kind == 'atom' and (text is None or node.text == text)


def _symbol(node):
    return (_atom(node) and bool(re.fullmatch(r'[a-zA-Z]', node.text))) or (
        node.kind == 'script' and node.text == '_' and _symbol(node.children[0]))


def _unwrap(node):
    while node.kind == 'seq' and len(node.children) == 1:
        node = node.children[0]
    return node


def _span(children, path=()):
    return Node('seq', children=list(children), path=path,
                units=sorted({i for c in children for i in c.units}))


def _spans(root):
    """등호 양쪽과 수치 부분식도 계산 후보에 포함한다."""
    for n in walk(root):
        if n.kind != 'seq': continue
        for start in range(len(n.children)):
            for stop in range(start + 2, len(n.children) + 1):
                if start == 0 and stop == len(n.children): continue
                first,last=n.children[start],n.children[stop-1]
                ops=('+','-',r'\times',r'\cdot','/','*',r'\div')
                if _atom(last) and last.text in ops:continue
                if _atom(first) and first.text in ops:
                    if first.text not in ('+','-') or (start>0 and not _atom(n.children[start-1],'=')):continue
                yield _span(n.children[start:stop], n.path + (start,))


def _power_bases(root):
    return {i for n in walk(root) if n.kind == 'script' and n.text == '^'
            for i in n.children[0].units}


def _subscript_owners(root):
    return {i: n.key() for n in walk(root) if n.kind == 'script' and '_' in n.text for i in n.units}


def _restriction_units(root):
    r"""\mid 아래의 제한 조건은 원래 식의 항과 연결하지 않는다."""
    return {
        i for n in walk(root)
        if (n.kind == 'script' and '_' in n.text
            and _atom(n.children[0], r'\mid'))
        for i in n.units
    }


def _aligned_substitutions(source, target):
    """불변 항으로 둘러싸인 변수/첨자 기호 → 수치 대입만 인정한다."""
    import difflib
    source, target = _unwrap(source), _unwrap(target)
    if _symbol(source) and numeric(target) is not None:
        yield source, target
        return
    if source.kind == target.kind == 'seq':
        def structural_items(n):
            return [c for c in n.children if not (_atom(c) and c.text in (r'\times', r'\cdot'))]
        a, b = structural_items(source), structural_items(target)
        matcher = difflib.SequenceMatcher(a=[n.key() for n in a], b=[n.key() for n in b], autojunk=False)
        for tag, i, j, k, l in matcher.get_opcodes():
            if tag == 'replace' and j-i == l-k == 1:
                yield from _aligned_substitutions(a[i], b[k])
    elif (source.kind == target.kind and source.kind in ('script', 'paren', 'frac', 'root')
          and source.text == target.text and len(source.children) == len(target.children)):
        for a, b in zip(source.children, target.children):
            yield from _aligned_substitutions(a, b)


def _function_call(children):
    children = [c for c in children if not (_atom(c) and c.text in ('=', r'\Rightarrow', r'\Longrightarrow'))]
    if len(children) != 2 or children[1].kind != 'paren': return None
    name = children[0]
    if _atom(name) and re.fullmatch('[a-zA-Z]',name.text):
        return name.text, 0, _unwrap(children[1].children[0]), name
    if (name.kind == 'script' and name.text == '^' and _atom(name.children[0])
        and name.children[1].kind == 'atom' and name.children[1].text == r'\prime'):
        return name.children[0].text, 1, _unwrap(children[1].children[0]), name
    return None


def _equation(root):
    indices = [i for i,c in enumerate(root.children) if _atom(c,'=')]
    # 맨 앞의 =는 식의 일부가 아닌 계속 기호이다.
    indices = [i for i in indices if i > 0]
    if len(indices) != 1: return None
    i=indices[0]
    return root.children[:i], root.children[i+1:]


def _polynomial_terms(children, variable):
    """명시적 함수 미분에서 사용하는 단항식 다항식의 제한된 인식기."""
    terms=[];current=[];sign=None
    def finish():
        if not current: return False
        pieces=[c for c in current if not (_atom(c) and c.text in (r'\times',r'\cdot'))]
        coefficient=None;base=None;exponent=None
        for c in pieces:
            if _atom(c,variable):
                if base is not None:return False
                base=c;degree=1
            elif c.kind=='script' and c.text=='^' and _atom(c.children[0],variable):
                if base is not None:return False
                value=numeric(c.children[1])
                if value is None or value.denominator!=1 or not 1<=value<=100:return False
                base,exponent,degree=c.children[0],c.children[1],int(value)
            elif numeric(c) is not None and coefficient is None: coefficient=c
            else:return False
        if base is None:degree=0
        value=numeric(coefficient) if coefficient is not None else Rational(1)
        if sign is not None and sign.text=='-':value=-value
        terms.append(dict(value=value,degree=degree,coefficient=coefficient,base=base,
                          exponent=exponent,sign=sign,units=[i for c in current for i in c.units]))
        return True
    for c in children:
        if _atom(c) and c.text in ('+','-'):
            if current:
                if not finish():return None
                current=[]
            elif sign is not None:return None
            sign=c
        else:current.append(c)
    if not finish():return None
    return terms


def _derivative_pairs(source, target):
    a,b=_equation(source),_equation(target)
    if a is None or b is None:return []
    af,bf=_function_call(a[0]),_function_call(b[0])
    if not af or not bf or af[:2]!=(bf[0],0) or bf[1]!=1 or af[2].key()!=bf[2].key():return []
    if not _atom(af[2]) or not re.fullmatch('[a-zA-Z]',af[2].text):return []
    src,tgt=_polynomial_terms(a[1],af[2].text),_polynomial_terms(b[1],af[2].text)
    if src is None or tgt is None:return []
    active=[s for s in src if s['degree']>0 and s['value']!=0]
    if len(active)!=len(tgt):return []
    pairs=[];remaining=list(tgt)
    for s in active:
        candidates=[t for t in remaining if t['degree']==s['degree']-1 and t['value']==s['value']*s['degree']]
        if len(candidates)!=1:return []
        t=candidates[0];remaining.remove(t);pairs.append((s,t))
    return pairs


def _limit_definition(source,target):
    """표준 미분계수 극한 정의에서 f'(a)로의 전환만 인식한다."""
    call=_function_call(target.children)
    if not call or call[1]!=1 or len(source.children)!=2:return []
    limit,fraction=source.children
    if not (limit.kind=='script' and limit.text=='_' and _atom(limit.children[0],r'\lim') and fraction.kind=='frac'):return []
    sub=_unwrap(limit.children[1])
    if sub.kind!='seq' or len(sub.children)!=3 or not (_atom(sub.children[1]) and sub.children[1].text in (r'\to',r'\rightarrow')):return []
    variable,point=sub.children[0],sub.children[2]
    num,den=_unwrap(fraction.children[0]),_unwrap(fraction.children[1])
    if num.kind!='seq' or den.kind!='seq' or len(num.children)!=5 or len(den.children)!=3:return []
    first,second=_function_call(num.children[:2]),_function_call(num.children[3:])
    if not first or not second or first[:2]!=(call[0],0) or second[:2]!=first[:2]:return []
    if not _atom(num.children[2],'-') or not _atom(den.children[1],'-'):return []
    if first[2].key()!=variable.key() or den.children[0].key()!=variable.key():return []
    if second[2].key()!=point.key() or den.children[2].key()!=point.key() or call[2].key()!=point.key():return []
    target_paren=next(n for n in target.children if n.kind=='paren')
    return [(first[3],call[3].children[0]),(num.children[4],target_paren)]


def context_substitutions(history, source_index, target, links, report, available):
    """실제로 기록된 대입 값만 다른 식에서 가져온다. 반환값은 대상→(식,토큰들)."""
    source=history[source_index]
    substitutions=list(_aligned_substitutions(source[0],target[0]))
    known=[]
    for index in sorted(available, reverse=True):
        eq=_equation(history[index][0])
        if eq is not None:
            lhs,rhs=_unwrap(_span(eq[0])),_unwrap(_span(eq[1]))
            if _symbol(lhs) and numeric(rhs) is not None:
                known.append((lhs.key(),numeric(rhs),index,rhs.units))
    # f'(x)=식과 f'(2)가 함께 있으면 식 속 x에 넣는 2의 실제 출처를 찾는다.
    source_body=[c for c in source[0].children if not _atom(c,'=')]
    source_eq=_equation(source[0])
    if source_eq is not None:source_body=source_eq[1]
    for definition in history[:source_index+1]:
        eq=_equation(definition[0])
        if eq is None:continue
        fn=_function_call(eq[0])
        if not fn or not _symbol(fn[2]) or _span(eq[1]).key()!=_span(source_body).key():continue
        for index in sorted(available,reverse=True):
            point=_function_call(history[index][0].children)
            if point and point[:2]==fn[:2] and numeric(point[2]) is not None:
                known.append((fn[2].key(),numeric(point[2]),index,point[2].units))
    result={}
    for s,t in substitutions:
        if s.kind == 'atom' and s.text == 'd':
            continue
        candidates=[v for v in known if v[0]==s.key() and v[1]==numeric(t) and v[2]!=source_index]
        if not candidates:continue
        _,_,index,units=candidates[0]
        for ti in t.units:
            if report[ti]['reason']=='substitution':result[ti]=(index,units)
    return result


def plan_latex(parsed, modes, overrides, sources=None, use_history=True):
    """이전 식 후보의 연결 품질로 출발식을 선택하고 대입 출처를 함께 기록."""
    count=len(parsed)-1
    sources=[None]*count if sources is None else list(sources)
    if len(sources)!=count:raise ValueError('sources 길이는 전환 개수와 같아야 합니다.')
    visible={0};plans=[]
    weights={'derivative-definition':8,'exact-structure':5,'equal-rational-value':5,'same-token':2,
             'same-base-merge':4,'same-token-branch':1,'substitution':2,'heuristic':-4,
             'derivative-coefficient':6,'derivative-exponent':6,'derivative-base':6,
             'derivative-constant':6,'derivative-sign':4,'new':0,'new-statement':0,'manual':5}
    for i,target in enumerate(parsed[1:],1):
        explicit=sources[i-1]
        if explicit is not None and (not isinstance(explicit,int) or explicit not in visible):
            raise ValueError(f'sources[{i-1}]는 앞에서 표시되고 아직 교체되지 않은 식 번호여야 합니다.')
        candidates=[explicit] if explicit is not None else (sorted(visible) if use_history and overrides[i-1] is None else [i-1])
        options=[]
        for j in candidates:
            links,report=match_latex(parsed[j],target,overrides[i-1])
            score=sum(weights.get(r['reason'],0) for r in report)
            # 차이가 작으면 직전 식을 택해 불필요하게 오래된 식으로 돌아가지 않는다.
            score+=4 if j==i-1 else 0
            options.append((score,j,links,report))
        _,j,links,report=max(options,key=lambda v:(v[0],v[1]))
        external=context_substitutions(parsed,j,target,links,report,visible)
        for r in report:
            r['source_step']=j
            if r['target'] in external:
                index,units=external[r['target']]
                r['sources']=list(units);r['source_step']=index;r['reason']='context-substitution'
        plans.append(dict(source=j,links=links,report=report,external=external))
        if modes[i-1]:visible.discard(j)
        visible.add(i)
    return plans


def match_latex(source, target, overrides=None):
    """target unit index -> source indices와 연결 근거를 반환한다. 입력 트리를 변경하지 않는다."""
    if overrides is not None and not isinstance(overrides, dict):
        raise TypeError('수동 연결은 {도착 번호: [출발 번호]} 사전이어야 합니다.')
    sr, su = source; tr, tu = target
    links, reasons, used = {}, {}, set()
    snodes, tnodes = list(walk(sr)) + list(_spans(sr)), list(walk(tr))
    source_bases,target_bases=_power_bases(sr),_power_bases(tr)
    so,to=_subscript_owners(sr),_subscript_owners(tr)
    source_restrictions,target_restrictions=_restriction_units(sr),_restriction_units(tr)
    def compatible(si,ti):
        if si in source_restrictions or ti in target_restrictions:
            return si in source_restrictions and ti in target_restrictions
        if (si in so or ti in to) and so.get(si)!=to.get(ti):return False
        a,b=role(su[si].path),role(tu[ti].path)
        restrictive={'exponent','subscript','numerator','denominator'}
        if re.fullmatch(r'\d+(?:\.\d+)?',su[si].tex) and ((a and a[-1] in restrictive) or (b and b[-1] in restrictive)):
            return a[-1:]==b[-1:]
        return True

    def assign(t, sources, why):
        links[t] = list(dict.fromkeys(sources)); reasons[t] = why; used.update(sources)

    def group(s, t, why):
        # 부분식 안에서 같은 글자를 먼저 연결하고 나머지를 계산 결과로 모은다.
        local_used = set()
        for ti in t.units:
            if ti in links:
                local_used.update(links[ti]); continue
            candidates = [si for si in s.units if si not in local_used and su[si].tex == tu[ti].tex]
            if candidates:
                si = min(candidates, key=lambda x: distance(su[x], tu[ti]))
                assign(ti, [si], why); local_used.add(si)
        pending = [ti for ti in t.units if ti not in links]
        rest = [si for si in s.units if si not in local_used]
        for j, ti in enumerate(pending):
            pool = rest or s.units
            chosen = pool[j * len(pool)//len(pending)]
            assign(ti, [chosen], why); local_used.add(chosen)
        leftovers = [si for si in s.units if si not in local_used]
        if leftovers:
            values = [ti for ti in t.units if re.fullmatch(r'\d+(?:\.\d+)?', tu[ti].tex)]
            target_id = (values or t.units)[0]
            assign(target_id, links.get(target_id, []) + leftovers, why)

    # 별개 풀이식의 등장은 기존 변수의 값 변경으로 취급하지 않는다.
    independent=(any(_atom(c,'=') for c in sr.children)
                 and not any(_atom(c,'=') for c in tr.children)
                 and ((len(tr.children)==1 and _symbol(tr.children[0]))
                      or (tr.children and (tr.children[0].kind=='script' and _atom(tr.children[0].children[0],r'\lim')))))
    if independent:
        for t in tu:assign(t.index,[],'new-statement')
    else:
        for s,t in _limit_definition(sr,tr):group(s,t,'derivative-definition')
        for s,t in _derivative_pairs(sr,tr):
            if t['coefficient'] is not None:
                nodes=[n for n in (s['coefficient'],s['exponent']) if n is not None]
                if not nodes:nodes=[s['base']]
                group(_span(nodes),t['coefficient'],'derivative-coefficient' if s['degree']>1 else 'derivative-constant')
            if t['base'] is not None:group(s['base'],t['base'],'derivative-base')
            if t['exponent'] is not None and s['exponent'] is not None:
                group(s['exponent'],t['exponent'],'derivative-exponent')
            if s['sign'] is not None and t['sign'] is not None:
                group(s['sign'],t['sign'],'derivative-sign')
        for s,t in _aligned_substitutions(sr,tr):
            if not any(i in links for i in t.units):group(s,t,'substitution')
        equation = _equation(tr)
        if _symbol(_unwrap(sr)) and equation is not None:
            lhs, rhs = equation
            if _span(lhs).key() == sr.key() and any(_symbol(c) for c in rhs):
                source_ids = [unit.index for unit in su if 'subscript' in unit.path]
                if not source_ids: source_ids = [unit.index for unit in su]
                for unit in _span(rhs).units:
                    assign(unit, source_ids, 'arithmetic-sequence-expansion')
        source_equation = _equation(sr)
        target_equals = [c for c in tr.children if _atom(c, '=')]
        if source_equation is not None and len(target_equals) >= 2 and any(_atom(c, 'd') for c in tr.children):
            source_ids = [unit.index for unit in su if 'subscript' in unit.path]
            for unit in tu:
                if unit.tex in ('3', 'd') and unit.path[:1] not in ((0,),):
                    assign(unit.index, source_ids, 'arithmetic-sequence-expansion')
    # 큰 공통 부분식을 먼저 확보해 반복되는 숫자의 잘못된 선점을 막는다.
    for t in sorted(tnodes, key=lambda n: -len(n.units)):
        if any(i in target_restrictions for i in t.units): continue
        if len(t.units) < 2 or any(i in links for i in t.units): continue
        candidates = [s for s in snodes if s.key() == t.key() and not used.intersection(s.units)]
        if candidates:
            s = min(candidates, key=lambda n: distance(su[n.units[0]], tu[t.units[0]]))
            group(s, t, 'exact-structure')
    # 작은 계산 부분식부터 연결한다. 지수 계산을 밑의 이동과 분리한다.
    if sum(_atom(c, '=') for c in sr.children) > 1:
        for t in sorted(tnodes, key=lambda n: len(n.units)):
            if t.kind != 'frac': continue
            for ti in t.units:
                if ti in links: continue
                candidates = [si for si in su if si.tex == tu[ti].tex and si.index not in used]
                if candidates:
                    si = min(candidates, key=lambda i: distance(i, tu[ti]))
                    assign(ti, [si.index], 'calculation-result')
    for t in sorted(tnodes, key=lambda n: len(n.units)):
        if any(i in target_restrictions for i in t.units): continue
        if all(i in links for i in t.units): continue
        value = numeric(t)
        if value is None: continue
        candidates = []
        for s in snodes:
            if s.key() == t.key() or numeric(s) != value: continue
            source_set, target_set = set(s.units), set(t.units)
            if any(set(links[ti]) - source_set for ti in t.units if ti in links): continue
            if any(source_set.intersection(sis) for ti, sis in links.items() if ti not in target_set): continue
            candidates.append(s)
        if candidates:
            s = min(candidates, key=lambda n: (distance(su[n.units[0]],tu[t.units[0]]), -len(n.units)))
            reason = 'calculation-result' if s.kind == 'frac' and t.kind == 'atom' else 'equal-rational-value'
            group(s, t, reason)
    for t in tu:
        if t.index in links: continue
        if t.index in target_restrictions: continue
        candidates = [s.index for s in su if s.tex == t.tex and s.index not in used and compatible(s.index,t.index)]
        if candidates:
            si = min(candidates, key=lambda i: distance(su[i], t))
            assign(t.index, [si], 'same-token')
    # 같은 밑을 합칠 때 나머지 밑도 결과의 밑까지 이동한다.
    for s in su:
        if s.index in used or s.index not in source_bases: continue
        candidates = [t.index for t in tu if t.index in target_bases and t.tex == s.tex and role(t.path) == role(s.path)]
        if len(candidates) == 1:
            ti = candidates[0]; assign(ti, links.get(ti, []) + [s.index], 'same-base-merge')
    # 1→N 동일 숫자·변수 분기. 새 연산기호는 별도로 등장한다.
    for t in tu:
        if t.index in links or not re.fullmatch(r'\d+(?:\.\d+)?|[a-zA-Z]', t.tex): continue
        if t.index in target_restrictions: continue
        candidates = [s.index for s in su if s.tex == t.tex and compatible(s.index,t.index)]
        if candidates:
            assign(t.index, [min(candidates,key=lambda i: distance(su[i],t))], 'same-token-branch')
    # 바뀐 숫자·변수만 가까운 역할끼리 연결한다.
    changed = [t for t in tu if t.index not in links and re.fullmatch(r'\d+(?:\.\d+)?|[a-zA-Z]',t.tex)]
    for s in su:
        if s.index in used or not re.fullmatch(r'\d+(?:\.\d+)?|[a-zA-Z]',s.tex) or not changed: continue
        t = min(changed,key=lambda t: distance(s,t))
        assign(t.index,links.get(t.index,[])+[s.index],'heuristic')
    for t in tu:
        if t.index not in links: assign(t.index, [], 'new')
    if overrides is not None:
        for ti, sis in overrides.items():
            sis = [sis] if isinstance(sis,int) else list(sis)
            if not isinstance(ti,int) or not 0 <= ti < len(tu) or any(not isinstance(si,int) or not 0 <= si < len(su) for si in sis):
                raise ValueError('수동 연결의 토큰 번호가 범위를 벗어났습니다. flow.latex_tokens(eq)로 확인하세요.')
            links[ti], reasons[ti] = list(dict.fromkeys(sis)), 'manual'
    report = [dict(target=t.index, tex=t.tex, path='.'.join(map(str,t.path)),
                   sources=links[t.index], reason=reasons[t.index]) for t in tu]
    return links, report


def render_latex(parsed):
    # 파싱과 매핑 테스트는 Manim 설치 없이도 실행 가능하다.
    from manim import VGroup, RIGHT
    from .mobjects import MathTex, Term, Fraction, Paren, _ordered_parts, _dynamic_family
    from reactive_manim import Root
    class LimitsTerm(Term):
        def compose_tex_string(self):
            self._term = self.register_child(self._term)
            self._superscript = self.register_child(self._superscript)
            self._subscript = self.register_child(self._subscript)
            self.child_components = [p for p in
                (self._term, self._superscript, self._subscript) if p is not None]
            tex = r"\mathop{" + self._term.get_tex_string() + r"}\limits"
            if self._superscript is not None:
                tex += "^{" + self._superscript.get_tex_string() + "}"
            if self._subscript is not None:
                tex += "_{" + self._subscript.get_tex_string() + "}"
            return tex

    root, units = parsed
    mobs = {}
    def build(n):
        children = [build(c) for c in n.children]
        if n.kind == 'atom': mob = MathTex(n.text)[0].clone()
        elif n.kind == 'seq':
            function_call = (
                len(n.children) == 2
                and _symbol(n.children[0])
                and n.children[1].kind == 'paren'
            )
            mob = VGroup(*children).arrange(RIGHT, buff=-0.08) if function_call else MathTex(*children)
        elif n.kind == 'frac': mob = Fraction(*children)
        elif n.kind == 'paren': mob = Paren(children[0])
        elif n.kind == 'root': mob = Root(*children)
        elif n.kind == 'script':
            args = dict(zip(n.text,children[1:]))
            cls = LimitsTerm if _atom(n.children[0], r'\lim') else Term
            mob = cls(children[0], superscript=args.get('^'), subscript=args.get('_'))
        else: raise LatexSyntaxError(f'지원하지 않는 구조: {n.kind}')
        mobs[id(n)] = mob
        return mob
    eq = build(root)
    bindings = {}
    for n in walk(root):
        child_ids = {p.id for c in n.children for p in _dynamic_family(mobs[id(c)])}
        own_parts = [p for p in _ordered_parts(mobs[id(n)]) if p.id not in child_ids]
        if not n.own: continue
        if len(n.own) == 1:
            bindings[n.own[0]] = own_parts
        elif n.kind == 'paren':
            middle = mobs[id(n)].get_center()[0]
            bindings[n.own[0]] = [p for p in own_parts if p.get_center()[0] < middle]
            bindings[n.own[1]] = [p for p in own_parts if p.get_center()[0] >= middle]
        if any(not bindings.get(i) for i in n.own):
            raise RuntimeError(f'LaTeX 도형 연결 실패: {n.path}, {n.kind}')
    return eq, bindings


def attach_mapping(source_bindings, target_bindings, links):
    from .mobjects import _set_link
    for ti, targets in target_bindings.items():
        sources = [p.id for si in links[ti] for p in source_bindings[si]]
        sources = tuple(dict.fromkeys(sources))
        for target in targets:
            _set_link(target, 'source_id', sources[0] if sources else None)
            _set_link(target, 'target_id', None)
            # 명시적인 빈 연결은 Flow가 새 글자로 표시하게 한다.
            target._change_source_ids = sources
