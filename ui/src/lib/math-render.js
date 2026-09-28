/* Converts the Russian spoken-math notation stored in tasks to MathML.
 * Unsupported or incomplete formulas stay as source text. */
(function (root) {
  const escapeXml = (value) =>
    String(value).replace(
      /[&<>"']/g,
      (c) =>
        ({
          "&": "&amp;",
          "<": "&lt;",
          ">": "&gt;",
          '"': "&quot;",
          "'": "&#39;",
        })[c],
    );
  const row = (parts) => `<mrow>${parts.join("")}</mrow>`;
  const operator = (value) => `<mo>${escapeXml(value)}</mo>`;
  const identifier = (value) => `<mi>${escapeXml(value)}</mi>`;
  const number = (value) => `<mn>${escapeXml(value)}</mn>`;

  const words = new Map(
    Object.entries({
      плюс: "+",
      минус: "−",
      "умножить на": "×",
      "делить на": "÷",
      больше: ">",
      меньше: "<",
      "больше или равно": "≥",
      "меньше или равно": "≤",
      "не равно": "≠",
      равносильно: "⇔",
      равно: "=",
      принадлежит: "∈",
      пересечение: "∩",
      объединение: "∪",
      альфа: "α",
      бета: "β",
      гамма: "γ",
      дельта: "δ",
      пи: "π",
      бесконечность: "∞",
      синус: "sin",
      косинус: "cos",
      тангенс: "tan",
      котангенс: "cot",
      арксинус: "arcsin",
      арккосинус: "arccos",
      арктангенс: "arctan",
      арккотангенс: "arccot",
      градус: "°",
      градуса: "°",
      градусов: "°",
      градусы: "°",
    }),
  );
  const latex = new Map(
    Object.entries({
      alpha: "α",
      beta: "β",
      gamma: "γ",
      delta: "δ",
      Delta: "Δ",
      omega: "ω",
      rho: "ρ",
      mu: "μ",
      pi: "π",
      tau: "τ",
      phi: "φ",
      Phi: "Φ",
      varphi: "φ",
      theta: "θ",
      lambda: "λ",
      sigma: "σ",
      epsilon: "ε",
      varepsilon: "ε",
      nu: "ν",
      eta: "η",
      partial: "∂",
      lg: "lg",
      pm: "±",
      approx: "≈",
      sim: "∼",
      mid: "∣",
      perp: "⟂",
      triangle: "△",
      cdot: "·",
      times: "×",
      div: "÷",
      ge: "≥",
      geq: "≥",
      geqslant: "≥",
      le: "≤",
      leq: "≤",
      leqslant: "≤",
      ne: "≠",
      neq: "≠",
      in: "∈",
      cup: "∪",
      cap: "∩",
      infty: "∞",
      Rightarrow: "⇒",
      leftarrow: "←",
      rightarrow: "→",
      quad: " ",
      qquad: " ",
      circ: "°",
      prime: "′",
      angle: "∠",
      equiv: "≡",
      bmod: "mod",
      oplus: "⊕",
      ldots: "…",
      "|": "∥",
      Sigma: "Σ",
      Pi: "Π",
      Omega: "Ω",
      vdots: "⋮",
      max: "max",
      min: "min",
      sin: "sin",
      cos: "cos",
      tan: "tan",
      ctg: "cot",
      tg: "tan",
    }),
  );
  const special = new Map(
    Object.entries({
      "дробь: числитель:": "frac",
      ", знаменатель:": "denom",
      "конец дроби": "endFrac",
      "целая часть:": "mixedWhole",
      "дробная часть:": "fractionalPart",
      "числитель:": "numerator",
      "корень из: начало аргумента:": "sqrt",
      "корень 3 степени из: начало аргумента:": "cuberoot",
      "конец аргумента": "endArg",
      "логарифм по основанию": "log",
      "десятичный логарифм": "commonLog",
      "система выражений": "system",
      "конец системы": "endSystem",
      "левая круглая скобка": "lparen",
      "правая круглая скобка": "rparen",
      "левая квадратная скобка": "lbracket",
      "правая квадратная скобка": "rbracket",
      "левая фигурная скобка": "lbrace",
      "правая фигурная скобка": "rbrace",
      "в квадрате": "square",
      "в кубе": "cube",
      "в степени": "power",
    }),
  );
  const units = new Set([
    "г",
    "кг",
    "мг",
    "т",
    "м",
    "см",
    "мм",
    "км",
    "с",
    "мс",
    "мкс",
    "ч",
    "мин",
    "л",
    "мл",
    "моль",
    "В",
    "мВ",
    "кВ",
    "А",
    "мА",
    "кА",
    "Н",
    "кН",
    "Дж",
    "кДж",
    "МДж",
    "Вт",
    "мВт",
    "кВт",
    "МВт",
    "Па",
    "кПа",
    "МПа",
    "К",
    "°C",
    "Кл",
    "мкКл",
    "мкФ",
    "нФ",
    "Ф",
    "Ом",
    "кОм",
    "МОм",
    "Гц",
    "Тл",
    "дптр",
    "Дптр",
  ]);
  const cyrillicNames = new Set([...units, "НОД", "НОК"]);
  const phrases = [...special.keys(), ...words.keys()].sort(
    (a, b) => b.length - a.length,
  );

  function tokenize(source) {
    const tokens = [];
    let i = 0;
    while (i < source.length) {
      if (/\s/u.test(source[i])) {
        i++;
        continue;
      }
      const indexedRoot =
        /^корень\s+(\d+)\s+степени из:\s*начало аргумента:/iu.exec(
          source.slice(i),
        );
      if (indexedRoot) {
        tokens.push({ type: "nroot", value: indexedRoot[1] });
        i += indexedRoot[0].length;
        continue;
      }
      let matched = false;
      for (const phrase of phrases) {
        if (source.slice(i, i + phrase.length).toLowerCase() !== phrase)
          continue;
        const before = source[i - 1] || "";
        const after = source[i + phrase.length] || "";
        if (
          (/[\p{L}]/u.test(phrase[0]) && /[\p{L}]/u.test(before)) ||
          (/[\p{L}]/u.test(phrase.at(-1)) && /[\p{L}]/u.test(after))
        )
          continue;
        tokens.push({ type: special.get(phrase) || "word", value: phrase });
        i += phrase.length;
        matched = true;
        break;
      }
      if (matched) continue;
      const tail = source.slice(i);
      const match = /^(\\[A-Za-z]+|\\\||\d+(?:[.,]\d+)?|[\p{L}]+|[^\s])/u.exec(
        tail,
      );
      if (!match) return null;
      const value = match[0];
      tokens.push({
        type:
          value[0] === "\\"
            ? "latex"
            : /^[\p{L}]+$/u.test(value)
              ? "name"
              : /^\d/u.test(value)
                ? "number"
                : "symbol",
        value,
      });
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
    const take = (type) => (at()?.type === type ? tokens[pos++] : null);

    function sequence(stop = [], splitComma = false) {
      const parts = [];
      const rows = [];
      while (at() && !stop.includes(at().type) && !stop.includes(at().value)) {
        if (splitComma && at().type === "symbol" && at().value === ",") {
          pos++;
          if (parts.length) rows.push(row(parts.splice(0)));
          continue;
        }
        const type = at().type;
        if (
          [
            "denom",
            "endFrac",
            "endArg",
            "endSystem",
            "rparen",
            "rbracket",
            "rbrace",
          ].includes(type) ||
          at().value === "}"
        ) {
          invalid = true;
          return null;
        }
        let item = atom();
        if (!item) return null;
        while (
          at() &&
          (["square", "cube", "power"].includes(at().type) ||
            at().value === "_" ||
            at().value === "^")
        ) {
          if (["square", "cube", "power"].includes(at().type)) {
            const kind = tokens[pos++].type;
            const exponent =
              kind === "square"
                ? number("2")
                : kind === "cube"
                  ? number("3")
                  : atom();
            if (!exponent) {
              invalid = true;
              return null;
            }
            item = `<msup>${item}${exponent}</msup>`;
          } else {
            const mark = tokens[pos++].value;
            const script = atom();
            if (!script) {
              invalid = true;
              return null;
            }
            item =
              mark === "_"
                ? `<msub>${item}${script}</msub>`
                : `<msup>${item}${script}</msup>`;
          }
        }
        parts.push(item);
      }
      if (splitComma) {
        if (parts.length) rows.push(row(parts));
        return rows.length
          ? `<mtable>${rows.map((value) => `<mtr><mtd>${value}</mtd></mtr>`).join("")}</mtable>`
          : null;
      }
      return parts.length ? row(parts) : null;
    }

    function atom() {
      const token = tokens[pos++];
      if (!token) return null;
      if (token.type === "frac") {
        const top = sequence(["denom"]);
        if (!top || !take("denom")) {
          invalid = true;
          return null;
        }
        const bottom = sequence(["endFrac"]);
        if (!bottom || !take("endFrac")) {
          invalid = true;
          return null;
        }
        return `<mfrac>${top}${bottom}</mfrac>`;
      }
      if (token.type === "mixedWhole") {
        const whole = take("number");
        if (!whole) {
          invalid = true;
          return null;
        }
        if (at()?.type === "symbol" && at().value === ",") pos++;
        if (!take("fractionalPart") || !take("numerator")) {
          invalid = true;
          return null;
        }
        const numeratorToken = take("number");
        if (!numeratorToken || !take("denom")) {
          invalid = true;
          return null;
        }
        const denominatorToken = take("number");
        if (!denominatorToken) {
          invalid = true;
          return null;
        }
        return row([
          number(whole.value),
          `<mfrac>${number(numeratorToken.value)}${number(denominatorToken.value)}</mfrac>`,
        ]);
      }
      if (token.type === "log" || token.type === "commonLog") {
        const base = token.type === "commonLog" ? number("10") : atom();
        const argument = atom();
        if (!base || !argument) {
          invalid = true;
          return null;
        }
        return row([`<msub><mi>log</mi>${base}</msub>`, argument]);
      }
      if (
        token.type === "sqrt" ||
        token.type === "cuberoot" ||
        token.type === "nroot"
      ) {
        const content = sequence(["endArg"]);
        if (!content || !take("endArg")) {
          invalid = true;
          return null;
        }
        if (token.type === "sqrt") return `<msqrt>${content}</msqrt>`;
        const index = token.type === "nroot" ? token.value : "3";
        return `<mroot>${content}${number(index)}</mroot>`;
      }
      if (token.type === "system") {
        const content = sequence(["endSystem"], true);
        if (!content || !take("endSystem")) {
          invalid = true;
          return null;
        }
        return `<mrow><mo>{</mo>${content}</mrow>`;
      }
      const pairs = {
        lparen: ["rparen", "(", ")"],
        lbracket: ["rbracket", "[", "]"],
        lbrace: ["rbrace", "{", "}"],
      };
      if (pairs[token.type]) {
        const [end, left, right] = pairs[token.type];
        const interval = token.type === "lparen" || token.type === "lbracket";
        const stops = interval ? ["rparen", "rbracket"] : [end];
        const contentStart = pos;
        const content = sequence(stops);
        const closing = at();
        if (!content || !closing || !stops.includes(closing.type)) {
          invalid = true;
          return null;
        }
        const mixed = closing.type !== end;
        const hasIntervalSeparator = tokens
          .slice(contentStart, pos)
          .some((t) => t.type === "symbol" && t.value === ";");
        if (mixed && !hasIntervalSeparator) {
          invalid = true;
          return null;
        }
        pos++;
        const closeMark = closing.type === "rbracket" ? "]" : ")";
        return row([operator(left), content, operator(closeMark)]);
      }
      if (token.type === "word") {
        const value = words.get(token.value);
        return [
          "sin",
          "cos",
          "tan",
          "cot",
          "arcsin",
          "arccos",
          "arctan",
          "arccot",
        ].includes(value)
          ? identifier(value)
          : operator(value);
      }
      if (token.type === "latex") {
        const command = token.value.slice(1);
        if (["frac", "dfrac", "tfrac"].includes(command)) {
          const numerator = atom();
          const denominator = atom();
          if (!numerator || !denominator) {
            invalid = true;
            return null;
          }
          return `<mfrac>${numerator}${denominator}</mfrac>`;
        }
        if (command === "sqrt") {
          const content = atom();
          if (!content) {
            invalid = true;
            return null;
          }
          return `<msqrt>${content}</msqrt>`;
        }
        if (command === "left" || command === "right") return "<mrow/>";
        if (command === "text") {
          if (at()?.type === "name" && /[А-Яа-яЁё]/u.test(at().value)) {
            return `<mtext>${escapeXml(tokens[pos++].value)}</mtext>`;
          }
          if (!at() || (at().type === "symbol" && /[.,;:]/u.test(at().value)))
            return "<mrow/>";
          invalid = true;
          return null;
        }
        if (command === "operatorname") {
          const next = at();
          if (next?.type === "word") {
            pos++;
            const name = words.get(next.value);
            if (
              [
                "sin",
                "cos",
                "tan",
                "cot",
                "arcsin",
                "arccos",
                "arctan",
                "arccot",
              ].includes(name)
            )
              return identifier(name);
          }
          if (next?.type === "name" && !/[А-Яа-яЁё]/u.test(next.value))
            return identifier(tokens[pos++].value);
          invalid = true;
          return null;
        }
        if (
          command === "mathrm" &&
          at()?.type === "name" &&
          !/[А-Яа-яЁё]/u.test(at().value)
        ) {
          return `<mi mathvariant="normal">${escapeXml(tokens[pos++].value)}</mi>`;
        }
        if (command === "vec") {
          const target = atom();
          return target ? `<mover>${target}${operator("→")}</mover>` : null;
        }
        if (/^vec[A-Za-z]$/.test(command))
          return `<mover>${identifier(command.at(-1))}${operator("→")}</mover>`;
        if (/^mathrm[A-Za-z]$/.test(command))
          return `<mi mathvariant="normal">${escapeXml(command.at(-1))}</mi>`;
        if (/^mathcal[A-Za-z]$/.test(command))
          return `<mi mathvariant="script">${escapeXml(command.at(-1))}</mi>`;
        if (/^overrightarrow[A-Za-z]$/.test(command))
          return `<mover>${identifier(command.at(-1))}${operator("→")}</mover>`;
        if (/^overline[A-Za-z]$/.test(command))
          return `<mover>${identifier(command.at(-1))}${operator("¯")}</mover>`;
        const value = latex.get(command);
        if (value == null) {
          invalid = true;
          return null;
        }
        return ["sin", "cos", "tan", "cot", "max", "min", "lg"].includes(value)
          ? identifier(value)
          : operator(value);
      }
      if (token.type === "number") return number(token.value);
      if (token.type === "name") {
        if (token.value.toLowerCase() === "градусовс")
          return "<mtext>°C</mtext>";
        if (
          /[А-Яа-яЁё]/u.test(token.value) &&
          !cyrillicNames.has(token.value)
        ) {
          invalid = true;
          return null;
        }
        if (units.has(token.value))
          return `<mtext>${escapeXml(token.value)}</mtext>`;
        return identifier(token.value);
      }
      if (token.type === "symbol") {
        if (token.value === "{") {
          const content = sequence(["}"]);
          if (!content || at()?.value !== "}") {
            invalid = true;
            return null;
          }
          pos++;
          return content;
        }
        if (token.value === "'") return operator("′");
        if (/^[=+\-*/<>|,;:.!?\[\](){}±×÷∞]$/u.test(token.value))
          return operator(token.value);
        invalid = true;
      }
      return null;
    }

    const body = sequence();
    if (!body || invalid || pos !== tokens.length) return null;
    return `<math xmlns="http://www.w3.org/1998/Math/MathML" aria-label="${escapeXml(source)}">${body}</math>`;
  }

  function renderMathText(element, value) {
    const source = String(value ?? "");
    const fragment = document.createDocumentFragment();
    let cursor = 0;
    while (cursor < source.length) {
      const start = source.indexOf("$", cursor);
      if (start < 0) break;
      const end = source.indexOf("$", start + 1);
      if (end < 0) break;
      fragment.append(document.createTextNode(source.slice(cursor, start)));
      const raw = source.slice(start, end + 1);
      const math = formulaToMathML(source.slice(start + 1, end));
      if (math) {
        const wrapper = document.createElement("span");
        wrapper.className = "inline-math";
        wrapper.innerHTML = math;
        fragment.append(wrapper);
      } else fragment.append(document.createTextNode(raw));
      cursor = end + 1;
    }
    fragment.append(document.createTextNode(source.slice(cursor)));
    element.replaceChildren(fragment);
  }

  root.taskMath = { formulaToMathML, renderMathText };
  if (typeof module !== "undefined") module.exports = root.taskMath;
})(globalThis);
