class Outer {
    constructor() {
        this.value = 42;
        
        function innerFunction() {
            return "inner";
        }
        
        this.getInnerClass = function() {
            class InnerClass {
                getValue() {
                    return innerFunction() + " value";
                }
            }
            return new InnerClass();
        };
    }
    
    method() {
        return function() {
            return this.value;
        }.bind(this);
    }
}

function outer() {
    class LocalClass {
        constructor() {
            this.name = "local";
        }
    }
    
    return new LocalClass();
}