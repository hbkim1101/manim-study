# 수식 버전을 미리 정의하는 Manim 풀이



## 극한 표시와 카메라 이동 수정

`\lim_{x\to2}`는 별도 옵션 없이 `x→2`를 lim의 정중앙 아래에 표시합니다. 위첨자가 있으면 위 중앙에 놓입니다. 일반 변수의 아래첨자는 기존 위치를 유지합니다.

카메라는 분기 시 먼저 `self.play(frame.animate...)`로 실제 출발식까지 부드럽게 이동합니다. 문제 2에서는 2번째 식으로 올라간 뒤, 다음 `self.play(수식 변환, frame.animate...)`에서 식 생성과 함께 5번째 식까지 내려옵니다. 올라가는 시간은 `camera_run_time`, 수식 생성과 함께 내려가는 시간은 `run_time`으로 조절합니다. `transition(..., focus=False)`는 카메라를 움직이지 않습니다.

## 문제 2·3 자동 연결 개선

노트북의 세 문제 모두 LaTeX 입력으로 변경했습니다. 별도 실행 예제는 `auto_latex_problems23.py`, 확인 영상은 `problem2_auto.mp4`, `problem3_auto.mp4`입니다.

- 문제 2: `2x^3 → 6x^2`에서 계수 2와 지수 3을 6으로 합치고, 지수 3은 2로도 분기합니다. `−x → −1`을 연결합니다.
- 표준 미분계수 극한 정의를 `f′(2)`로 연결합니다. 이후 앞의 도함수 `6x²−1`에서 다시 출발하고, `f′(2)`에 있는 2를 밑에 대입합니다. 지수 2와 대입하는 2를 구분합니다. 최종 결과는 23입니다.
- 문제 3: 별개 식 `a_7`은 새로 등장합니다. `a_2` 전체가 값 2로 변하며, `d`에 넣을 3은 앞서 표시한 `d=3`에서 복사합니다. 최종 결과는 17입니다.
- 재생 전후 원본 수식의 값, ID, 링크, 도형이 같은지 검사했습니다. 두 문제 모두 `strict=True`로 실제 렌더했고, 기존 문제 1도 회귀 렌더했습니다.

미분 인식은 `f(x)=다항식 → f^{\prime}(x)=다항식`으로 명시된 일차 미분 중 지원하는 단항식의 합에 한정됩니다. 결과의 계수·차수가 맞을 때만 해당 규칙을 적용합니다. 곱/합성함수의 일반적인 미분은 처리하지 않습니다. 대입 출처는 입력한 식들에서 확인된 값만 사용하며, 문제 3의 주어진 값 `a_2=2`를 PDF에서 읽거나 추론하지는 않습니다. 다음 LaTeX에 적힌 2가 결과입니다.

```bash
python -m unittest discover -s tests -p 'test_auto_latex*.py'
python -m manim -ql tests/test_problems23_render.py Problem2Tests Problem3Tests
python -m manim -ql auto_latex_problems23.py Problem2 Problem3
```

## 최신 기능: LaTeX만 작성하면 자동으로 이어 붙이기

```python
flow.play_latex(
    r"2^{\frac{3}{2}} \times 4^{-\frac{1}{2}}",
    r"= 2^{\frac{3}{2}} \times (2^2)^{-\frac{1}{2}}",
    r"= 2^{\frac{3}{2}} \times 2^{2\times(-\frac{1}{2})}",
    r"= 2^{\frac{3}{2}} \times 2^{-1}",
    r"= 2^{\frac{3}{2}-1}",
    r"= 2^{\frac{1}{2}}",
)
flow.finish()
```

`module/auto_latex.py`를 **추가**하고, `module/simple_solution_flow.py`와 노트북을 교체하세요. 전체 실행 예제는 `auto_latex_demo.py`, 렌더 결과는 `auto_latex_demo.mp4`입니다. 기존 `mobjects.py`도 압축에 포함되어 있습니다. PDF 없이 데모를 실행할 수 있습니다.

### 먼저 정의하고 나중에 재생하기

```python
eq1, eq1_1, eq2 = flow.latex_steps(
    r"d=\frac{9}{3}",
    r"d=3",
    r"a_7=2+5\cdot3",
    same_line=[True, False],
)
flow.stack(eq1, eq1_1, eq2)
flow.play_linear()
```

`same_line` 기본값은 `False`: 앞 식을 남기고 다음 줄로 복사합니다. `True`는 같은 자리에서 교체합니다. 목록이면 각 전환별로 지정하며 길이는 식 개수보다 하나 적어야 합니다. 원본 변수의 수식·도형은 재생 후에도 유지됩니다.

### 자동 연결 기준

1. 큰 공통 부분식을 먼저 고정해 같은 숫자가 다른 곳으로 잘못 연결되는 것을 줄입니다.
2. 밑·지수·분자·분모의 구조와 순서를 비교합니다.
3. 정확한 유리수로 같은 값인 부분식을 찾아 계산/전개를 연결합니다. `4 → 2²`, `2×(-1/2) → -1`, `3/2−1 → 1/2`를 포함합니다. 지수 계산이 밑으로 합쳐지지 않도록 작은 부분식부터 처리합니다.
4. 같은 밑의 병합과 동일 숫자·변수의 분기를 연결합니다.
5. 남은 숫자·변수 변경은 구조/순서에 따른 휴리스틱으로 연결하고, 새 기호는 등장시킵니다.

다음 식을 자동으로 고치거나 계산해 대체하지 않습니다. 다음 식의 수학적 내용은 입력이 기준이고, 계산은 연결 출처를 찾는 데만 사용합니다. 원문을 `eval`로 실행하지 않습니다.

### 연결 확인과 수동 보정

```python
eq1, eq2 = flow.latex_steps(r"x+y", r"y+x")
print(flow.latex_tokens(eq1))
print(flow.latex_tokens(eq2))
print(flow.mapping_report(eq2))

# 목적지 토큰 0 ← 출발 2, 목적지 토큰 2 ← 출발 0
# 각 식의 토큰 번호는 latex_tokens로 확인합니다.
eq1, eq2 = flow.latex_steps(
    r"x+y", r"y+x",
    links=[{0: [2], 2: [0]}],
)
```

`links`의 목록 길이는 전환 개수입니다. `None`인 전환/지정하지 않은 토큰은 자동 매핑합니다. 빈 출발 목록 `[]`은 새로 등장시킵니다. 여러 출발 번호는 하나로 병합하고, 같은 출발 번호를 여러 목적지에 지정하면 분기합니다.

보고서의 `reason`은 `exact-structure`, `equal-rational-value`, `same-token`, `same-base-merge`, `same-token-branch`, `heuristic`, `new`, `manual` 중 하나입니다. `strict=True`는 `heuristic` 연결이 남으면 재생 전에 오류를 냅니다. 이는 수학적 의도의 완전한 증명이나 모든 중복 기호의 정답 보장을 뜻하지 않습니다.

자동 연결은 기본적으로 **아직 화면에 남아 있는 이전 식들**도 비교합니다. 문제 2처럼 앞의 도함수로 돌아오는 분기를 `play_linear()`에서도 자동 재생합니다. `use_history=False`이면 출발식 후보를 직전 식으로 제한합니다(알려진 대입 값의 외부 참조는 유지).

`sources=[0, 1, 2, 1, 4, 5, 6]`처럼 전환별 출발식 번호를 지정할 수도 있습니다. 번호는 입력 식 목록의 0부터 시작하는 인덱스입니다. `None`은 자동 선택이며, 이미 같은 자리에서 교체되어 사라진 식은 출발식으로 지정할 수 없습니다. `links`를 지정한 전환은 `sources`가 없으면 직전 식의 토큰 번호를 사용합니다. 다른 출발식으로 `transition()`을 직접 호출하려면 정의할 때 `sources`도 맞춰 주세요.

보고서의 `source_step`은 실제 출발식 번호입니다. `context-substitution`인 토큰은 별도 식의 번호와 토큰 번호를 가리킵니다. 추가 연결 근거는 `substitution`, `new-statement`, `derivative-coefficient`, `derivative-exponent`, `derivative-base`, `derivative-constant`, `derivative-sign`, `derivative-definition`, `context-substitution`입니다.

### 지원 범위와 제한

- 분수, 지수, 아래첨자, 둥근 괄호, 루트/근지수, 숫자/변수, 등록된 기호·연산자·함수명.
- `\left(...\right)`, `\frac`, `\sqrt`, `\times`, `\cdot`, `\lim`, `\sum`, 일반 그리스 문자 등의 등록 명령.
- `align`, 행렬, cases, 임의 사용자 매크로, `\text`, 대괄호 등은 아직 자동 파서 대상이 아닙니다. 지원하지 않는 명령은 명시적으로 거부합니다. 기존 구조 API는 계속 사용할 수 있습니다.
- 기본 Reactive Manim 수식 스타일로 렌더합니다. `\dfrac`·`\tfrac`는 `\frac`로, 둥근 괄호는 자동 크기 괄호로 정규화하며 명시적 공백 명령은 생략합니다. 원문의 수학적 내용은 유지하지만 픽셀/간격/글꼴 크기까지 동일한 LaTeX 레이아웃 엔진은 아닙니다.
- 어떤 수학 변형이든 의도한 출처를 항상 복원하는 CAS/증명기는 아닙니다. 반복 기호, 분배·인수분해, 지원 범위를 벗어난 미분·복합 치환 등은 연결 보정이 필요할 수 있습니다. 기존 수동 매핑 애니메이션과 모든 프레임의 동일성을 보장하지 않습니다.

### 이번 검증

- 핵심 6단계에 휴리스틱 값 변경이 없는지, 4의 분기, 지수 이동, 지수 계산의 역할 분리, 두 밑의 병합, 분수 계산을 검증했습니다.
- 파서/매퍼 회귀 테스트 총 17개 통과. 지원하지 않는 명령과 잘못된 입력, 수동 보정, 결정적 결과도 포함합니다.
- 실제 Manim 렌더에서 수식 도형과 토큰의 대응, 원본 보존, 같은 자리/다음 줄 혼합 재생, 수동 보정을 확인했습니다.
- 분수·루트·근지수·아래첨자·미분 기호·극한 식의 렌더 바인딩도 검사했습니다.
- Python 3.12 / Manim 0.19.0 / reactive-manim 0.0.5에서 검증했습니다. 사용자 PDF와 Windows/MiKTeX 환경은 이번 테스트에 포함하지 않았습니다.

```bash
python -m unittest discover -s tests -p test_auto_latex.py
python -m manim -ql tests/test_auto_latex_render.py AutoLatexTests
python -m manim -ql auto_latex_demo.py AutoLatexDemo
```

## 추가 개선: 복잡한 재조합을 한 줄로

```python
eq3 = flow.flatten_power(eq2)
eq4 = flow.set_exponent(eq3, 3, -1)
eq5 = flow.combine_powers(eq4)
eq6 = flow.set_exponent(eq5, 1, Fraction(1, 2))
```

이전의 `q[0], q[1], q[2]` 재나열과 `.base.inner.base` 접근을 내부에서 처리합니다. 기존 `evolve(..., build=...)`도 그대로 사용할 수 있습니다.

| 새 함수 | 동작 |
|---|---|
| `flow.flatten_power(eq)` | 최상위 `(a^m)^n` 후보 하나를 찾아 `a^(m×(n))`로 펼침 |
| `flow.flatten_power(eq, 3)` | 지정 항만 펼침. `'2.numerator'` 같은 중첩 경로도 가능 |
| `flow.combine_powers(eq)` | 최상위 `a^m × a^n` 또는 `a^m · a^n` 후보 한 쌍을 `a^(m+n)`으로 결합 |
| `flow.combine_powers(eq, 1, 3)` | 곱셈 기호로 연결된 두 항을 명시적으로 결합 |
| `flow.set_base(eq, 3, 2)` | 지정 거듭제곱의 밑만 변경 |
| `flow.set_exponent(eq, 3, -1)` | 지정 거듭제곱의 지수만 변경 |
| `flow.rewrite(eq, 2, 함수)` | 선택한 항만 재조합. 다른 항은 자동으로 유지 |

새 함수들은 `same_line=False`가 기본입니다. 기존 자리를 바꾸려면 `same_line=True`를 지정하세요. 기존 `change_at`, `append` 등의 기본값은 바꾸지 않았습니다.

```python
# 분수 하나만 뒤집기. p는 선택한 분수의 독립 사본.
eq2 = flow.rewrite(eq1, 2, lambda p: Fraction(p.denominator, p.numerator))

# 같은 자리에서 지수 수정
eq2_1 = flow.set_exponent(eq2, 3, -1, same_line=True)
```

자동 선택은 최상위 후보가 정확히 하나일 때만 작동합니다. 후보가 없거나 여러 개면 오류에 후보 위치를 안내하므로 명시적으로 선택하세요. 중첩 위치의 자동 검색은 하지 않습니다. `combine_powers`는 곱셈 기호가 사이에 있는 같은 밑만 허용하며 덧셈·나눗셈·다른 밑은 거부합니다. 밑의 같음은 TeX 공백을 제외한 문자열로 비교합니다.

이 함수들은 수식 구조 편집기입니다. `Term`·`Paren`·`Fraction`으로 구성한 식을 다루며, 하나의 LaTeX 문자열을 자동 파싱하거나 지수 값을 자동 계산하지 않습니다. 적용할 지수법칙의 수학적 조건은 사용자가 판단합니다. `flatten_power`는 한 겹을 펼치므로 더 깊은 중첩은 다음 단계에서 다시 호출할 수 있습니다.

원본의 값·ID·도형 보존, 새 함수의 글자별 출처 연결, 개별 색상 보존, 자동 선택의 모호성/잘못된 입력을 검사했습니다. 간소화한 문제 1과 `ConvenienceTests` 장면을 실제로 렌더했습니다. 추가 검증은 다음 명령으로 실행합니다.

```bash
python -m manim -ql tests/test_snapshot_flow.py ConvenienceTests
```

## 파일 적용

- `module/mobjects.py`: 기존 파일을 교체합니다.
- `module/simple_solution_flow.py`: 함께 교체하거나 새로 넣습니다.
- `sol_ex_simple.ipynb`: 세 문제를 새 방식으로 작성한 예제입니다.
- 기존 프로젝트의 `module/pdf_tools.py`, `math_2709.pdf`는 그대로 사용합니다. 이 파일들은 첨부에 없어 포함하지 않았습니다.
- PDF 없이 확인하려면 노트북의 `USE_PDF = False`로 바꾸세요.

## 핵심 사용법

```python
eq1 = MathTex(r"a_{10}-a_7", "=", "9")
eq1_1 = flow.insert(eq1, 1, ["=", 3, "d"])

eq2 = flow.evolve(eq1_1, build=lambda q: MathTex(
    q[1][2], q[2], Fraction(q[3], q[1][1]),
))
eq2_1 = flow.change_at(eq2, 2, 3)

flow.stack(eq1, eq1_1, eq2, eq2_1)
flow.play_linear()
```

`eq1`과 `eq1_1`은 독립 객체입니다. 같은 자리 변환 시 화면에서 원본이 사라져도 원본 변수의 수식은 유지됩니다. `eq1_1`의 이름은 규칙이 아니라 일반 Python 변수명입니다. 같은 자리 여부는 함수의 `same_line` 인수가 정합니다.

| 함수 | 반환값 | 기본 배치/재생 방식 |
|---|---|---|
| `flow.evolve(eq, {경로: 새 값})` | 새 수식 | 다음 줄, 앞 식 유지 |
| `flow.evolve(eq, build=lambda q: ...)` | 독립 사본 `q`로 만든 새 수식 | 다음 줄, 앞 식 유지 |
| `flow.change_at(eq, 경로, 값)` | 지정 항을 바꾼 새 수식 | 같은 자리 변환 |
| `flow.insert(eq, 위치, 값)` | 항을 삽입한 새 수식 | 같은 자리 변환 |
| `flow.append(eq, *값)` | 항을 추가한 새 수식 | 같은 자리 변환 |
| `flow.collapse_from(eq, 시작, 값, stop=None)` | 선택 범위를 합친 새 수식 | 같은 자리 변환 |
| `flow.inject_copy(eq, 경로, 외부항)` | 외부항의 복사 출처를 기록한 새 수식 | 같은 자리 변환 |
| `equation(*항)` | 입력 항을 복사한 `MathTex` | 배치/재생 없음 |
| `copy_eq(eq)` | 이전 단계의 링크를 정리한 독립 사본 | 배치/재생 없음 |
| `part(eq, "2.base.inner")` | 해당 내부 객체 | 변경 없음 |

모든 편집 함수는 자동 재생하지 않으므로 **반환값을 반드시 변수로 받으세요.** `same_line=False`를 주면 수정 함수로 만든 식도 앞 식을 남기며 다음 줄로 이동합니다. `flow.evolve(..., same_line=True)`도 가능합니다.

## 경로와 삽입 순서

```python
eq2 = flow.evolve(eq1, {"2.base": Paren(Term(2, 2))}, inserts=[(0, "=")])
```

변경 경로는 삽입 전 식을 기준으로 합니다. 변경 → 최상위 항 삭제 → 삽입 순서로 적용합니다. 여러 삽입은 작성 순서대로 적용하며 앞 삽입에 의해 밀린 인덱스를 사용합니다. 리스트를 `insert`로 넣으면 한 그룹으로 들어갑니다. 여러 최상위 항은 `inserts=[(1, "="), (2, 3), (3, "d")]`처럼 지정하세요.

`collapse_from(eq, 1, 24, stop=4)`는 Python 슬라이스처럼 `[1:4]`만 합칩니다. `stop`을 생략하면 마지막 항까지 포함합니다. 이 함수는 계산기가 아니므로 새 값은 사용자가 지정합니다. 예제의 `6·2²−1`은 `24−1`을 거쳐 `23`으로 수정했습니다.

## 구조 재조합과 분기

```python
eq2 = flow.evolve(eq1, build=lambda q: MathTex(q[0], Fraction(q[2], q[1])))
eq3 = flow.evolve(eq1, {"1": 7})  # 같은 원본에서 별도 분기
```

`build`에는 원본을 복사한 `q`가 전달됩니다. 콜백 안에서 외부 `eq1`을 직접 수정하지 마세요. 콜백 없이 기존 항을 직접 조합할 때는 `equation(eq1[0], eq1[2])`를 사용하세요. `MathTex(eq1[0], eq1[2])`처럼 원본 항을 직접 연결하면 Reactive Manim의 자동 부모 재연결이 일어날 수 있습니다. `Fraction(eq1[0], eq1[1])` 등의 내부 생성자도 마찬가지이므로 `build` 안에서 만들거나 각 입력을 복사하세요.

## 재생과 표시

```python
flow.stack(eq1, eq2, eq3, eq3_1)
flow.play_linear([eq1, eq2])
flow.transition(eq1, eq3)       # 표시된 원본에서 분기
flow.transition(eq3, eq3_1)    # 같은 자리 변경
```

다른 식에서 `inject_copy`할 때는 해당 외부항이 있는 식을 먼저 표시해야 합니다. 이미 같은 자리 변환으로 사라진 원본을 다시 표시하려면 `flow.begin(eq1)`을 사용하세요.

`SolutionFlow`는 식의 일반 Manim 도형 사본을 화면에 표시합니다. 출처가 연결된 항은 실제로 이동/변형하며, 여러 항은 결과 위치까지 겹쳐진 후 결과 하나만 남습니다. 입력 식 객체는 애니메이션 컨테이너로 사용하지 않습니다. 따라서 재생 중에도 정의해 둔 수식들의 값과 도형이 보존됩니다.

스타일과 배치는 재생 전에 정의하세요. 표시 후 수식 객체를 직접 `.set_color()` 또는 `.shift()`로 바꿔도 이미 표시한 사본에는 자동 반영되지 않습니다. 또한 `scene.add(eq)`와 `flow.begin(eq)`를 같은 식에 중복 사용하지 마세요. `flow.displays[id(eq)][0]`이 실제 화면 객체입니다.

기존 `TransformInStages` 직접 호출 API는 유지하지만, Flow의 재생은 별도의 스냅샷 변환입니다. Reactive Manim의 세부 `config` 옵션이나 자동 updater 연동을 그대로 제공하지는 않습니다. `run_time`, `pause`, `camera_run_time`은 `SolutionFlow(...)`, `lag_ratio`는 `transition(...)`에서 설정할 수 있습니다.

## 검증

Python 3.12, Manim 0.19.0, reactive-manim 0.0.5에서 검증했습니다.

- 세 문제의 수식 정의와 애니메이션을 저화질 MP4로 실제 렌더하고 마지막 화면을 확인했습니다.
- 원본의 TeX, ID/추적 링크, 부모 연결, 도형 좌표가 편집/재생 후에도 유지되는지 검사했습니다.
- 같은 원본에서 분기, N→M 출처 연결, 잘못된 경로/범위, 같은 행 배치, 삽입 색상 상속을 검사했습니다.
- 기존 `TransformInStages.from_copy()`와 `progress()`의 N→1 병합도 렌더했습니다.
- 다른 식에서 숫자를 복사하는 예제도 렌더했습니다. 같은 ID를 가진 여러 버전 중 실제로 지정한 식의 항에서 출발하도록 표시 객체를 찾습니다.

검증 장면은 `tests/test_snapshot_flow.py`에 있습니다. 프로젝트 루트에서 다음처럼 실행할 수 있습니다.

```bash
python -m manim -ql tests/test_snapshot_flow.py SnapshotTests LegacyTests LegacyProgressTests
```

문제 PDF와 `pdf_tools.py`는 제공되지 않아 PDF 로딩을 제외한 수식/애니메이션을 검증했습니다. Windows의 MiKTeX 및 사용자 설치 버전 조합은 이 환경에서 직접 검증하지 않았습니다.
