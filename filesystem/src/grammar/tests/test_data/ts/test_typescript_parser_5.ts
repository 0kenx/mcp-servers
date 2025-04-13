/**
 * User class.
 */
class User {
    // Properties with type annotations
    private id: number;
    public name: string;
    protected email: string;
    readonly createdAt: Date;
    
    // Constructor with parameter properties
    constructor(
        id: number,
        name: string,
        email: string,
        readonly role: string = "user"
    ) {
        this.id = id;
        this.name = name;
        this.email = email;
        this.createdAt = new Date();
    }
    
    // Method with return type
    public getInfo(): string {
        return `${this.name} (${this.email})`;
    }
}