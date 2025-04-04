class PrivateMembers {
    #privateField = 42;
    publicField = "public";
    
    constructor() {
        this.#initializePrivate();
    }
    
    #initializePrivate() {
        console.log("Private initialization");
    }
    
    get #privateValue() {
        return this.#privateField;
    }
    
    set #privateValue(value) {
        this.#privateField = value;
    }
    
    publicMethod() {
        return this.#privateField;
    }
}