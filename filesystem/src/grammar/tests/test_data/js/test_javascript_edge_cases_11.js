function sum(...numbers) {
    return numbers.reduce((total, n) => total + n, 0);
}

const obj1 = { a: 1, b: 2 };
const obj2 = { ...obj1, c: 3 };

function processConfig({ name, ...rest }) {
    console.log(name);
    return rest;
}

const array1 = [1, 2, 3];
const array2 = [...array1, 4, 5];