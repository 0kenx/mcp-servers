/**
 * A simple TypeScript program demonstrating language features
 * with some edge cases for parser testing
 */

// Basic type annotations
let id: number = 5;
let name: string = \"test\";
let isActive: boolean = true;
let mixed: any = \"anything\";

// Union type and type alias
type StringOrNumber = string | number;
let value: StringOrNumber = 42;

// Function with typed parameters and return type
function calculate(x: number, y: number = 10): number {
  return x + y;
}

// Generic function
function identity<T>(arg: T): T {
  return arg;
}

// Interface with optional properties
interface User {
  id: number;
  name: string;
  email?: string;
  readonly createdAt: Date;
}

// Implementing an interface
class UserAccount implements User {
  id: number;
  name: string;
  readonly createdAt: Date = new Date();
  
  constructor(id: number, name: string) {
    this.id = id;
    this.name = name;
  }
  
  printDetails(): void {
    console.log(`User: ${this.name} (${this.id})`);
  }
}

// Export named members
export { UserAccount, identity };
export type { User, StringOrNumber };

