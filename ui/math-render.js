/* Converts the Russian spoken-math notation stored in tasks to MathML.
 * Unsupported or incomplete formulas stay as source text. */
(function (root) {
  const escapeXml = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const row = parts => `<mrow>${parts.join('')}</mrow>`;
  const operator = value => `<mo>${escapeXml(value)}</mo>`;
  const identifier = value => `<mi>${escapeXml(value)}</mi>`;
  const number = value => `<mn>${escapeXml(value)}</mn>`;

  const words = new Map(Object.entries({
    'плюс': '+', 'минус': '−', 'умножить на': '×', 'делить на': '÷',
    'больше': '>', 'меньше': '<', 'больше или равно': '≥',
    'меньше или равно': '≤', 'не равно': '≠', 'равно': '=',
    'принадлежит': '∈', 'пересечение': '∩', 'объединение': '∪',
    'альфа': 'α', 'бета': 'β', 'гамма': 'γ', 'дельта': 'δ',
    'пи': 'π', 'бесконечность': '∞',
    'синус': 'sin', 'косинус': 'cos', 'тангенс': 'tan', 'котангенс': 'cot'
  }));
  const latex = new Map(Object.entries({
    alpha:'α', beta:'β', gamma:'γ', delta:'δ', Delta:'Δ', omega:'ω',
    rho:'ρ', mu:'μ', pi:'π', tau:'τ', phi:'φ', Phi:'Φ', varphi:'φ',
    theta:'θ', lambda:'λ', sigma:'σ', epsilon:'ε', varepsilon:'ε',
    nu:'ν', partial:'∂', lg:'lg',
    pm:'±', cdot:'·', times:'×', div:'÷', ge:'≥', geq:'≥',
    geqslant:'≥', le:'≤', leq:'≤', leqslant:'≤', ne:'≠',
    neq:'≠', in:'∈', cup:'∪', cap:'∩', infty:'∞',
    Rightarrow:'⇒', leftarrow:'←', rightarrow:'→',
    quad:' ', qquad:' ', circ:'°', prime:'′', angle:'∠',
    equiv:'≡', bmod:'mod', oplus:'⊕', ldots:'…', '|':'∥',
    sin:'sin', cos:'cos', tan:'tan', ctg:'cot', tg:'tan'
  }));
  const special = new Map(Object.entries({
    'дробь: числитель:':'frac', ', знаменатель:':'denom', 'конец дроби':'endFrac',
    'корень из: начало аргумента:':'sqrt',
    'корень 3 степени из: начало аргумента:':'cuberoot', 'конец аргумента':'endArg',
    'система выражений':'system', 'конец системы':'endSystem',
    'левая круглая скобка':'lparen', 'правая круглая скобка':'rparen',
    'левая квадратная скобка':'lbracket', 'правая квадратная скобка':'rbracket',
    'левая фигурная скобка':'lbrace', 'правая фигурная скобка':'rbrace',
    'в квадрате':'square', 'в кубе':'cube', 'в степени':'power'
  }));
  const cyrillicNames = new Set(['г','кг','м','см','мм','км','с','мс','ч','мин','В','А','Н','Дж','Вт','Па','К','НОД','НОК']);
  const phrases = [...special.keys(), ...words.keys()].sort((a, b) => b.length - a.length);

  function tokenize(source) {
    const tokens = [];
    let i = 0;
    while (i < source.length) {
      if (/\s/u.test(source[i])) { i++; continue; }
      let matched = false;
      for (const phrase of phrases) {
        if (source.slice(i, i + phrase.length).toLowerCase() !== phrase) continue;
        const before = source[i - 1] || '';
        const after = source[i + phrase.length] || '';
        if ((/[\p{L}]/u.test(phrase[0]) && /[\p{L}]/u.test(before)) ||
            (/[\p{L}]/u.test(phrase.at(-1)) && /[\p{L}]/u.test(after))) continue;
        tokens.push({type: special.get(phrase) || 'word', value: phrase});
        i += phrase.length;
        matched = true;
        break;
      }
      if (matched) continue;
      const tail = source.slice(i);
      const match = /^(\\[A-Za-z]+|\\\||\d+(?:[.,]\d+)?|[\p{L}]+|[^\s])/u.exec(tail);
      if (!match) return null;
      const value = match[0];
      tokens.push({type: value[0] === '\\' ? 'latex' : /^[\p{L}]+$/u.test(value) ? 'name' : /^\d/u.test(value) ? 'number' : 'symbol', value});
      i += value.length;
    }
    return tokens;
  }

  function formulaToMathML(source) {
    const tokens = tokenize(source);
    if (!tokens || !tokens.length) return null;
    let pos = 0;
    let invalid = false;
    const at = () => tokens[pos];
    const take = type => at()?.type === type ? tokens[pos++] : null;

    function sequence(stop = []) {
      const parts = [];
      while (at() && !stop.includes(at().type)) {
        const type = at().type;
        if (['denom','endFrac','endArg','endSystem','rparen','rbracket','rbrace'].includes(type)) { invalid = true; return null; }
        let item = atom();
        if (!item) return null;
        while (at() && (['square','cube','power'].includes(at().type) || at().value === '_' || at().value === '^')) {
          if (['square','cube','power'].includes(at().type)) {
            const kind = tokens[pos++].type;
            const exponent = kind === 'square' ? number('2') : kind === 'cube' ? number('3') : atom();
            if (!exponent) { invalid = true; return null; }
            item = `<msup>${item}${exponent}</msup>`;
          } else {
            const mark = tokens[pos++].value;
            const script = atom();
            if (!script) { invalid = true; return null; }
            item = mark === '_' ? `<msub>${item}${script}</msub>` : `<msup>${item}${script}</msup>`;
          }
        }
        parts.push(item);
      }
      return parts.length ? row(parts) : null;
    }

    function atom() {
      const token = tokens[pos++];
      if (!token) return null;
      if (token.type === 'frac') {
        const top = sequence(['denom']);
        if (!top || !take('denom')) { invalid = true; return null; }
        const bottom = sequence(['endFrac']);
        if (!bottom || !take('endFrac')) { invalid = true; return null; }
        return `<mfrac>${top}${bottom}</mfrac>`;
      }
      if (token.type === 'sqrt' || token.type === 'cuberoot') {
        const content = sequence(['endArg']);
        if (!content || !take('endArg')) { invalid = true; return null; }
        return token.type === 'sqrt' ? `<msqrt>${content}</msqrt>` : `<mroot>${content}${number('3')}</mroot>`;
      }
      if (token.type === 'system') {
        const content = sequence(['endSystem']);
        if (!content || !take('endSystem')) { invalid = true; return null; }
        return `<mrow><mo>{</mo><mtable><mtr><mtd>${content}</mtd></mtr></mtable></mrow>`;
      }
      const pairs = {lparen:['rparen','(',')'], lbracket:['rbracket','[',']'], lbrace:['rbrace','{','}']};
      if (pairs[token.type]) {
        const [end, left, right] = pairs[token.type];
        const content = sequence([end]);
        if (!content || !take(end)) { invalid = true; return null; }
        return row([operator(left), content, operator(right)]);
      }
      if (token.type === 'word') {
        const value = words.get(token.value);
        return ['sin','cos','tan','cot'].includes(value) ? identifier(value) : operator(value);
      }
      if (token.type === 'latex') {
        const command = token.value.slice(1);
        if (command === 'left' || command === 'right') return '<mrow/>';
        if (command === 'vec') {
          const target = atom();
          return target ? `<mover>${target}${operator('→')}</mover>` : null;
        }
        if (/^vec[A-Za-z]$/.test(command)) return `<mover>${identifier(command.at(-1))}${operator('→')}</mover>`;
        const value = latex.get(command);
        if (value == null) { invalid = true; return null; }
        return ['sin','cos','tan','cot'].includes(value) ? identifier(value) : operator(value);
      }
      if (token.type === 'number') return number(token.value);
      if (token.type === 'name') {
        if (/[А-Яа-яЁё]/u.test(token.value) && !cyrillicNames.has(token.value)) { invalid = true; return null; }
        return identifier(token.value);
      }
      if (token.type === 'symbol') {
        if (/^[=+\-*/<>|,;:.!?\[\](){}±×÷∞]$/u.test(token.value)) return operator(token.value);
        invalid = true;
      }
      return null;
    }

    const body = sequence();
    if (!body || invalid || pos !== tokens.length) return null;
    return `<math xmlns="http://www.w3.org/1998/Math/MathML" aria-label="${escapeXml(source)}">${body}</math>`;
  }

  function renderMathText(element, value) {
    const source = String(value ?? '');
    const fragment = document.createDocumentFragment();
    let cursor = 0;
    while (cursor < source.length) {
      const start = source.indexOf('$', cursor);
      if (start < 0) break;
      const end = source.indexOf('$', start + 1);
      if (end < 0) break;
      fragment.append(document.createTextNode(source.slice(cursor, start)));
      const raw = source.slice(start, end + 1);
      const math = formulaToMathML(source.slice(start + 1, end));
      if (math) {
        const wrapper = document.createElement('span');
        wrapper.className = 'inline-math';
        wrapper.innerHTML = math;
        fragment.append(wrapper);
      } else fragment.append(document.createTextNode(raw));
      cursor = end + 1;
    }
    fragment.append(document.createTextNode(source.slice(cursor)));
    element.replaceChildren(fragment);
  }

  root.taskMath = {formulaToMathML, renderMathText};
  if (typeof module !== 'undefined') module.exports = root.taskMath;
})(globalThis);
