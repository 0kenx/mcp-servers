class Base {
public:
    virtual void foo() = 0;
    virtual ~Base() = default;
};

class InterfaceA {
public:
    virtual void methodA() = 0;
    virtual ~InterfaceA() = default;
};

class InterfaceB {
public:
    virtual void methodB() = 0;
    virtual ~InterfaceB() = default;
};

// Multiple inheritance
class Derived : public Base, public InterfaceA, public InterfaceB {
public:
    void foo() override {
        // Implementation
    }
    
    void methodA() override {
        // Implementation
    }
    
    void methodB() override {
        // Implementation
    }
};

// Virtual inheritance (diamond problem)
class BaseV {
public:
    int x;
};

class Derived1 : virtual public BaseV {
public:
    int y;
};

class Derived2 : virtual public BaseV {
public:
    int z;
};

class Diamond : public Derived1, public Derived2 {
public:
    int w;
};