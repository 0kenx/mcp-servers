/**
 * Represents a person.
 */
class Person {
    /**
     * Create a person.
     */
    constructor(name, age) {
        this.name = name;
        this.age = age;
    }
    
    /**
     * Get a greeting from the person.
     */
    greet() {
        return `Hello, my name is ${this.name}!`;
    }
    
    // Static method
    static create(name, age) {
        return new Person(name, age);
    }
}