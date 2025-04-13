/**
 * Complex JavaScript program demonstrating advanced language features
 * for parser robustness testing
 */

// Imports with various syntaxes
import defaultExport from './module.js';
import * as namespace from './namespace.js';
import { export1, export2 as alias2 } from './named-exports.js';

// Unusual variable declarations and complex destructuring -> NOT DETECTED
const [a, , ...rest] = [1, 2, 3, 4, 5];
let { 
  prop: renamed, 
  obj: { 
    nested,
    ['computed' + 'Key']: computedValue = 'default' 
  } = {} 
} = { prop: 'value', obj: { nested: true, computedKey: 'test' } };

// Class with private fields, static methods and getters/setters
class ParserTest {  //    -> DETECTION ERROR: class: ParserTest (lines 22-262)
  #privateField = 42; //  -> NOT DETECTED
  static counter = 0; //  -> NOT DETECTED
  
  constructor(value) {
    this.value = value;
    ParserTest.counter++;
    this.#privateMethod();
  }
  
  //incompleteMethod( { // Incomplete method  -> NOT DETECTED
  //  console.log(
  
  // Private method  -> NOT DETECTED
  #privateMethod() {
    console.log('Private method called');
    return this.#privateField;
  }
  
  // Method with unusual name  -> NOT DETECTED
  'method with spaces'() {
    return this.value;
  }
  
  // Getter with complex logic
  get complexGetter() {
    try {
      return this.value ?? this.#privateField;
    } catch (e) {
      throw new Error('Failed in getter');
    }
  }
  
  // Setter with validation
  set complexSetter(newValue) {
    if (typeof newValue !== 'number') {
      throw new TypeError('Expected number');
    }
    this.value = newValue;
  }
  
  // Static method
  static create(...args) {
    return new ParserTest(...args);
  }
  
  // Generator method  -> NOT DETECTED
  *generator() {
    yield this.value;
    yield* [1, 2, 3].map(x => x * this.value);
  }
  
  // Async method with try/catch and await
  async fetchData() {
    try {
      const response = await fetch('https://api.example.com/data');
      const data = await response.json();
      return data;
    } catch (error) {
      console.error(error);
      return null;
    }
  }
}

// Proxy object with unusual handlers
const handler = { //   -> NOT DETECTED
  get(target, prop) { // Detected
    if (prop in target) {
      return target[prop];
    }
    
    // Return a function for any property access
    return function(...args) {
      console.log(`Called non-existent property ${prop} with args:`, args);
      return args.length > 0 ? args[0] : undefined;
    };
  },
  
  set(target, prop, value) {
    // Conditional property setting
    if (typeof value === 'function') {
      target[prop] = (...args) => value.apply(null, args);
    } else {
      target[prop] = value;
    }
    return true;
  },
  
  has(target, prop) {
    if (prop.startsWith('_')) {
      return false; // Hide properties starting with underscore
    }
    return prop in target;
  }
};

const proxiedObject = new Proxy({}, handler); //  -> NOT DETECTED ----- EVERYTHING A MESS FROM HERE -------

// Complex async/await pattern with Promise chaining   -> NOT DETECTED
async function complexAsyncFunction(input) {
  const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
  
  // Nested async IIFE with arrow function
  const result = await (async () => {
    await delay(100);
    
    // Promise.all with complex transforms
    const values = await Promise.all([
      Promise.resolve(1).then(x => x * 2),
      Promise.resolve(2).then(async x => {
        await delay(50);
        return x * 3;
      }),
      (async function() {
        try {
          return await Promise.resolve(input);
        } catch {
          return 0;
        }
      })()
    ]);
    
    return values.reduce((sum, val) => sum + val, 0);
  })();
  
  // Switch statement with fall-through
  switch (result) {
    case 10:
      console.log('Exactly 10');
      break;
    case 15:
      console.log('Exactly 15');
      // Intentional fall-through
    default:
      console.log('Default case');
  }
  
  return result;
}

// Object with unusual property names and methods
const complexObject = {
  'property:with:colons': true,
  123: 'numeric property',
  [Symbol('symbol key')]: 'symbol value',
  [\"nested\" + \"Keys\"](param1, param2) {
    return param1 + param2;
  },
  get [`dynamic${Math.random() > 0.5 ? 'True' : 'False'}`]() {
    return Math.random();
  },
  __proto__: {
    inheritedMethod() {
      return 'from prototype';
    }
  }
};

// Event loop manipulation with microtasks and macrotasks
function eventLoopTest() {
  console.log('Start');
  
  setTimeout(() => {
    console.log('Timeout 1');
    Promise.resolve().then(() => console.log('Promise in timeout'));
  }, 0);
  
  Promise.resolve()
    .then(() => {
      console.log('Promise 1');
      return new Promise(resolve => {
        setTimeout(() => {
          console.log('Nested timeout in promise');
          resolve('Resolved value');
        }, 0);
      });
    })
    .then(value => {
      console.log('Promise 2 with:', value);
      
      queueMicrotask(() => {
        console.log('Microtask queued from promise');
      });
    });
  
  console.log('End');
}

// Regular expressions with lookahead, lookbehind and named capture groups
const complexRegex = /^(?<prefix>https?:\\/\\/)(?:www\\.)?(?<domain>[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)+)(?<path>\\/(?:[\\w\\d\\._~:/?#[\\]@!$&'()*+,;=.-]|%[0-9A-F]{2})*)?(?<query>\\?(?:[\\w\\d\\._~:/?#[\\]@!$&'()*+,;=.-]|%[0-9A-F]{2})*)?$/i;

// Tagged template function
function tagged(strings, ...values) {
  return strings.reduce((result, str, i) => {
    return result + str + (values[i] || '');
  }, '');
}

// Dynamic import with complex handling
function loadModule(name) {
  return import(`./modules/${name}.js`)
    .then(module => {
      if ('default' in module) {
        return module.default;
      }
      return Object.fromEntries(
        Object.entries(module).map(([key, value]) => [
          key.startsWith('_') ? key.slice(1) : key,
          typeof value === 'function' ? value.bind(module) : value
        ])
      );
    })
    .catch(error => {
      console.error(`Failed to load module ${name}:`, error);
      throw new Error(`Module loading failed: ${error.message}`);
    });
}

// Export with unusual syntax
export {
  ParserTest,
  complexAsyncFunction as async,
  complexObject as obj,
  eventLoopTest as testEventLoop,
  complexRegex as regex,
  tagged,
  loadModule as load,
};

// Export default as an anonymous class
export default class {
  constructor() {
    console.log('Anonymous default export instantiated');
  }
  
  toString() {
    return 'DefaultExport';
  }
};

