namespace Outer {
    int global_var = 42;
    
    namespace Inner {
        void inner_function() {
            // Implementation
        }
        
        class InnerClass {
        public:
            void method() {}
        };
    }
    
    class OuterClass {
    public:
        class NestedClass {
        public:
            void nested_method() {}
            
            struct DeepNested {
                int x, y;
            };
        };
        
        void outer_method() {}
    };
    
    namespace {
        // Anonymous namespace
        int anon_var = 10;
        
        void anon_function() {
            // Implementation
        }
    }
}

// C++17 nested namespace definition
namespace A::B::C {
    void abc_function() {
        // Implementation
    }
    
    class ABC {
    public:
        void method() {}
    };
}