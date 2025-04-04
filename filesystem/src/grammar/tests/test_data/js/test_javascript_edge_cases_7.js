const propertyName = "dynamicProp";
const obj = {
    [propertyName]: "value",
    ["static" + "Property"]: true,
    [1 + 2]: "three"
};

class ComputedMethods {
    ["method" + 1]() {
        return "method1";
    }
    
    get [Symbol.toStringTag]() {
        return "ComputedMethods";
    }
    
    set [propertyName](value) {
        this._value = value;
    }
}