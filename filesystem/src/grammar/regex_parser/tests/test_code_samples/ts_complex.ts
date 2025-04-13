/**
 * Complex TypeScript program demonstrating advanced language features
 * for parser robustness testing
 */

// Import with different syntaxes
import BaseModule from './base-module';
import * as Utils from './utils';
import { Feature1, Feature2 as RenamedFeature } from './features';
import type { TypeOnly } from './types';

// Namespace for organizing code
namespace ParserTest {
  // Exported interface with complex types
  export interface Config<T extends object = any> {
    readonly id: string;
    options?: Partial<T>;
    callbacks: {
      onSuccess: (data: T) => void;
      onError: (error: Error) => never;
      onProgress?: (percent: number) => unknown;
    };
    metadata: Record<string, any>;
  }
  
  // Type with conditional types, mapped types and template literals
  export type ApiEndpoints<T extends string> = {
    [K in T as `get${Capitalize<K>}`]: (id: number) => Promise<unknown>;
  } & {
    [K in T as `update${Capitalize<K>}`]: (id: number, data: unknown) => Promise<boolean>;
  };
  
  // Utility types
  export type Nullable<T> = T | null;
  export type DeepReadonly<T> = T extends (infer R)[] 
    ? DeepReadonlyArray<R> 
    : T extends object 
      ? DeepReadonlyObject<T> 
      : T;
  
  interface DeepReadonlyArray<T> extends ReadonlyArray<DeepReadonly<T>> {}
  
  type DeepReadonlyObject<T> = {
    readonly [P in keyof T]: DeepReadonly<T[P]>;
  };
  
  // Enum with mixed string and numeric values
  export enum Status {
    Pending = 0,
    Active = 'ACTIVE',
    Suspended = 2,
    Deleted = 'DELETED',
  }
  
  //export enum Incomplete {
  //  Done = 0,
  //  Pending = 'Pen...
  
  // Abstract class with generic parameters and decorators
  @sealed
  export abstract class BaseService<T, U = any> {
    protected config: Config<T>;
    
    constructor(config: Config<T>) {
      this.config = config;
    }
    
    @logMethod
    public async initialize(): Promise<boolean> {
      try {
        await this.connect();
        return true;
      } catch (error) {
        this.handleError(error as Error);
        return false;
      }
    }
    
    @deprecated('Use connect() instead')
    protected async setup(): Promise<void> {
      return this.connect();
    }
    
    protected abstract connect(): Promise<void>;
    protected abstract handleError(error: Error): void;
    
    // Method with overloads
    public fetch(): Promise<U[]>;
    public fetch(id: number): Promise<U>;
    public fetch(id?: number): Promise<U | U[]> {
      return id !== undefined 
        ? this.fetchOne(id) 
        : this.fetchAll();
    }
    
    protected abstract fetchOne(id: number): Promise<U>;
    protected abstract fetchAll(): Promise<U[]>;
  }
  
  // Function decorator
  function logMethod(
    target: any, 
    propertyKey: string, 
    descriptor: PropertyDescriptor
  ) {
    const originalMethod = descriptor.value;
    
    descriptor.value = function(...args: any[]) {
      console.log(`Calling ${propertyKey} with:`, args);
      try {
        const result = originalMethod.apply(this, args);
        if (result instanceof Promise) {
          return result.then(
            value => {
              console.log(`${propertyKey} resolved with:`, value);
              return value;
            },
            error => {
              console.error(`${propertyKey} rejected with:`, error);
              throw error;
            }
          );
        }
        console.log(`${propertyKey} returned:`, result);
        return result;
      } catch (error) {
        console.error(`${propertyKey} threw:`, error);
        throw error;
      }
    };
    
    return descriptor;
  }
  
  // Class decorator
  function sealed(constructor: Function) {
    Object.seal(constructor);
    Object.seal(constructor.prototype);
  }
  
  // Property decorator
  function deprecated(message: string = 'This member is deprecated') {
    return function(
      target: any,
      propertyKey: string,
      descriptor?: PropertyDescriptor
    ) {
      if (descriptor) {
        const original = descriptor.value;
        descriptor.value = function(...args: any[]) {
          console.warn(`Warning: ${propertyKey} is deprecated. ${message}`);
          return original.apply(this, args);
        };
        return descriptor;
      } else {
        // Property decorator
        let value = target[propertyKey];
        const getter = function() {
          console.warn(`Warning: ${propertyKey} is deprecated. ${message}`);
          return value;
        };
        const setter = function(newVal: any) {
          console.warn(`Warning: ${propertyKey} is deprecated. ${message}`);
          value = newVal;
        };
        
        Object.defineProperty(target, propertyKey, {
          get: getter,
          set: setter,
          enumerable: true,
          configurable: true
        });
      }
    };
  }
  
  // Implementation class with mixins and complex inheritance
  type Constructor<T = {}> = new (...args: any[]) => T;
  
  function Timestamped<TBase extends Constructor>(Base: TBase) {
    return class extends Base {
      timestamp = new Date();
      
      getTimestamp(): Date {
        return this.timestamp;
      }
    };
  }
  
  function Loggable<TBase extends Constructor>(Base: TBase) {
    return class extends Base {
      log(message: string): void {
        console.log(`[${new Date().toISOString()}] ${message}`);
      }
    };
  }
  
  abstract class EntityBase {
    id: number = 0;
  }
  
  // Class with mixins applied
  export class UserService extends Timestamped(Loggable(BaseService<UserData, User>)) {
    @deprecated()
    private legacyData?: string[];
    
    // Property with complex type
    private users: Map<number, Nullable<DeepReadonly<User>>> = new Map();
    
    constructor(config: Config<UserData>) {
      super(config);
      this.initializeCache();
    }
    
    private initializeCache(): void {
      // Do nothing in this example
    }
    
    protected async connect(): Promise<void> {
      // Implementation omitted
    }
    
    protected handleError(error: Error): void {
      this.log(`Error in UserService: ${error.message}`);
      this.config.callbacks.onError(error);
    }
    
    protected async fetchOne(id: number): Promise<User> {
      // Implementation with tuple type
      const [user, permissions]: [User, string[]] = await Promise.all([
        this.fetchUserData(id),
        this.fetchPermissions(id)
      ]);
      
      user.permissions = permissions;
      return user;
    }
    
    protected async fetchAll(): Promise<User[]> {
      // Implementation with array destructuring
      const ids = Array.from(this.users.keys());
      return Promise.all(ids.map(id => this.fetchOne(id)));
    }
    
    private async fetchUserData(id: number): Promise<User> {
      // Using type assertion
      return { id, name: `User ${id}` } as User;
    }
    
    private async fetchPermissions(id: number): Promise<string[]> {
      return ['read', 'write'];
    }
    
    // Method with complex generic constraints
    public async transform<R extends Record<string, any>, K extends keyof User>(
      user: User,
      keys: K[],
      transformer: (values: Pick<User, K>) => R
    ): Promise<R> {
      const picked = keys.reduce((obj, key) => {
        obj[key] = user[key];
        return obj;
      }, {} as Pick<User, K>);
      
      return transformer(picked);
    }
    
    // Async generator method
    public async *streamUsers(): AsyncGenerator<User, void, unknown> {
      const ids = Array.from(this.users.keys());
      for (const id of ids) {
        yield await this.fetchOne(id);
        await new Promise(resolve => setTimeout(resolve, 100));
      }
    }
  }
  
  // Type for use in service
  export interface User {
    id: number;
    name: string;
    email?: string;
    permissions?: string[];
    status?: Status;
  }
  
  // Type alias for complex union
  export type UserData = 
    | { type: 'basic'; data: Omit<User, 'permissions'> }
    | { type: 'full'; data: User }
    | { type: 'minimal'; data: Pick<User, 'id' | 'name'> };
  
  // Utility function with function overloads and rest parameters
  export function createUser(): User;
  export function createUser(id: number): User;
  export function createUser(id: number, name: string): User;
  export function createUser(
    id?: number,
    name?: string,
    ...extraFields: [string, any][]
  ): User {
    const user: User = {
      id: id ?? Math.floor(Math.random() * 1000),
      name: name ?? `User ${id}`
    };
    
    for (const [key, value] of extraFields) {
      (user as any)[key] = value;
    }
    
    return user;
  }
  
  // Nested namespace
  export namespace Utils {
    export function isActive(user: User): boolean {
      return user.status === Status.Active;
    }
    
    export function canPerform(
      user: User,
      action: string,
      resource: { type: string; id: number }
    ): boolean {
      const { permissions = [] } = user;
      return permissions.includes(action) || permissions.includes('admin');
    }
  }
}

// Module augmentation
declare module './utils' {
  export interface UtilityFunctions {
    formatUser(user: ParserTest.User): string;
  }
}

// Declaration merging with interface
interface Window {
  userService?: ParserTest.UserService;
}

// Export statements
export * from './submodule';
export { ParserTest };

