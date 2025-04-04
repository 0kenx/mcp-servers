/**
 * JavaScript validation file with complex but valid language features to test parser robustness
 */

// Complex imports using various syntaxes
import defaultExport from './module.js';
import * as namespace from './namespace.js';
import { export1, export2 as alias2 } from './named-exports.js';
import('./dynamic-import.js').then(module => console.log(module));

// Complex destructuring with defaults and rest
const { 
  a: renamedA = 10, 
  b: { 
    c: { 
      d = 42 
    } = {}
  } = { c: {} }, 
  ...restObj 
} = { a: 5, b: { c: {} }, extra1: 'value1', extra2: 'value2' };

const [first, , ...restArr] = [1, 2, 3, 4, 5];

// Class with all modern features
class ComplexClass {
  // Private fields
  #privateField = 42;
  #privateObj = { key: 'value' };
  
  // Static initialization block
  static {
    this.staticInitValue = 'initialized';
    console.log('Class initialization');
  }
  
  // Static private field and method
  static #instanceCount = 0;
  static get instanceCount() {
    return this.#instanceCount;
  }
  
  // Instance public fields
  publicField = 'public';
  
  // Complex constructor with parameter destructuring
  constructor({ 
    name = 'default', 
    config: { 
      debug = false, 
      level = 1 
    } = {} 
  } = {}) {
    this.name = name;
    this.debug = debug;
    this.level = level;
    ComplexClass.#instanceCount++;
  }
  
  // Private method
  #privateMethod() {
    return this.#privateField;
  }
  
  // Method with complex parameter and return
  processData(data, { transform = x => x, validate = false } = {}) {
    try {
      const result = transform(data);
      
      if (validate && typeof this.validate === 'function') {
        return this.validate(result) ? result : null;
      }
      
      return result;
    } catch (error) {
      console.error(`Error processing data: ${error.message}`);
      throw new Error(`Processing failed: ${error.message}`);
    }
  }
  
  // Getter with complex logic
  get complexValue() {
    return this.#privateMethod() * this.level;
  }
  
  // Setter with validation
  set complexValue(newValue) {
    if (typeof newValue !== 'number') {
      throw new TypeError('Expected a number');
    }
    
    this.#privateField = newValue / this.level;
  }
  
  // Generator method
  *generateSequence(start = 0, end = 10, step = 1) {
    for (let i = start; i < end; i += step) {
      yield i;
    }
  }
  
  // Async method with try/catch
  async fetchData(url, { 
    headers = {}, 
    timeout = 5000, 
    retries = 3 
  } = {}) {
    let lastError;
    
    for (let attempt = 0; attempt < retries; attempt++) {
      try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), timeout);
        
        const response = await fetch(url, { 
          headers, 
          signal: controller.signal 
        });
        
        clearTimeout(timeoutId);
        
        if (!response.ok) {
          throw new Error(`HTTP error: ${response.status}`);
        }
        
        return await response.json();
      } catch (error) {
        console.warn(`Attempt ${attempt + 1} failed: ${error.message}`);
        lastError = error;
        
        if (error.name === 'AbortError') {
          console.warn('Request timed out');
        }
        
        // Wait before retry
        await new Promise(resolve => setTimeout(resolve, 1000));
      }
    }
    
    throw lastError || new Error('All retry attempts failed');
  }
  
  // Method with complex callback usage
  withCallbacks(callbacks = {}) {
    const { 
      onStart = () => {}, 
      onProgress = (percent) => {}, 
      onComplete = (result) => {}, 
      onError = (error) => {} 
    } = callbacks;
    
    try {
      onStart();
      
      for (let i = 0; i <= 100; i += 10) {
        onProgress(i);
      }
      
      const result = this.#privateMethod();
      onComplete(result);
      return result;
    } catch (error) {
      onError(error);
      throw error;
    }
  }
  
  // Method with dynamic key
  ['method_' + (() => 'dynamic')()]() {
    return 'Dynamic method';
  }
  
  // toString override
  toString() {
    return `ComplexClass(name: ${this.name}, level: ${this.level})`;
  }
  
  // Static factory method
  static create(config) {
    return new ComplexClass(config);
  }
}

// Proxy with complex behavior
const handler = {
  get(target, prop, receiver) {
    console.log(`Getting ${prop}`);
    
    if (prop in target) {
      const value = Reflect.get(target, prop, receiver);
      
      // Wrap functions to add logging
      if (typeof value === 'function') {
        return function(...args) {
          console.log(`Calling ${prop} with args:`, args);
          return value.apply(this === receiver ? target : this, args);
        };
      }
      
      return value;
    }
    
    // Dynamic property creation
    if (prop.startsWith('compute')) {
      const suffix = prop.slice(7); // remove 'compute'
      return (x) => {
        if (suffix === 'Square') return x * x;
        if (suffix === 'Double') return x * 2;
        return x;
      };
    }
    
    return undefined;
  },
  
  set(target, prop, value, receiver) {
    console.log(`Setting ${prop} to ${value}`);
    
    // Add validation
    if (prop === 'age' && (typeof value !== 'number' || value < 0)) {
      throw new TypeError('Age must be a positive number');
    }
    
    return Reflect.set(target, prop, value, receiver);
  }
};

const proxiedObject = new Proxy({
  name: 'ProxyObject',
  greet() {
    return `Hello, ${this.name}!`;
  }
}, handler);

// Complex async/await with Promise patterns
async function complexAsyncFunction(input) {
  const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
  
  // Nested async IIFE with Promise.all
  const result = await (async () => {
    await delay(100);
    
    // Process in parallel
    const values = await Promise.all([
      Promise.resolve(1).then(x => x * 2),
      new Promise(resolve => setTimeout(() => resolve(input * 3), 50)),
      (async () => {
        try {
          await delay(30);
          return input * 4;
        } catch {
          return 0;
        }
      })()
    ]);
    
    return values.reduce((sum, val) => sum + val, 0);
  })();
  
  // Advanced pattern with Promise chaining
  const processedResult = await Promise.resolve(result)
    .then(async r => {
      await delay(50);
      return r * 2;
    })
    .then(r => r.toString())
    .then(str => ({ value: str, length: str.length }))
    .catch(error => {
      console.error('Error in processing:', error);
      return { error: error.message };
    })
    .finally(() => {
      console.log('Processing complete');
    });
  
  return processedResult;
}

// Function using advanced array and object features
function advancedDataManipulation(data = []) {
  const processedData = data
    // Map values
    .map((item, index) => ({
      ...item,
      index,
      processed: true
    }))
    // Filter out undefined or null
    .filter(Boolean)
    // Complex filtering
    .filter(({ value, type }) => 
      typeof value !== 'undefined' && 
      (type === 'normal' || value > 10)
    )
    // Custom sorting
    .sort((a, b) => {
      if (a.priority !== b.priority) {
        return b.priority - a.priority; // Higher priority first
      }
      return a.index - b.index; // Original order
    })
    // Reduce to grouped object
    .reduce((acc, item) => {
      const { type = 'default' } = item;
      
      if (!acc[type]) {
        acc[type] = [];
      }
      
      acc[type].push(item);
      return acc;
    }, {});
  
  // Object manipulation with dynamic keys
  const result = Object.entries(processedData).reduce((acc, [key, values]) => {
    acc[`group_${key}`] = {
      count: values.length,
      sum: values.reduce((sum, { value = 0 }) => sum + value, 0),
      items: values.map(({ id, value }) => ({ id, value }))
    };
    return acc;
  }, {});
  
  return {
    summary: {
      totalGroups: Object.keys(result).length,
      totalItems: Object.values(result).reduce((sum, { count }) => sum + count, 0)
    },
    data: result
  };
}

// Tagged template literals with complex processing
function tag(strings, ...values) {
  return strings.reduce((result, str, i) => {
    const value = values[i] || '';
    
    // Process string part
    const processedStr = str
      .trim()
      .replace(/\s+/g, ' ');
    
    // Process value part
    const processedValue = typeof value === 'object'
      ? JSON.stringify(value)
      : String(value);
    
    return result + processedStr + processedValue;
  }, '');
}

const taggedResult = tag`
  This is a ${'complex'} template
  with multiple ${123} values and
  even ${{ objects: true, nested: { value: 42 } }}
`;

// Export default and named exports
export { advancedDataManipulation, complexAsyncFunction, tag };
export default ComplexClass; 