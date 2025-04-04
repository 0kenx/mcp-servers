const greeting = (name, age) => `Hello ${name}, you are ${age > 18 ? "an adult" : "a minor"}!`;
const html = `
  <div class="${isActive ? 'active' : 'inactive'}">
    ${items.map(item => `<p>${item.name}</p>`).join('')}
  </div>
`;