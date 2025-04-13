// This has C-style syntax
void c_function(int x) {
    printf("Value: %d\\n", x);
    return;
}

// This has Java-style syntax
public class JavaClass {
    private int value;
    
    public JavaClass(int value) {
        this.value = value;
    }
    
    public int getValue() {
        return this.value;
    }
}

// This has JavaScript-style syntax
function jsFunction() {
    const obj = {
        key: "value",
        method: function() {
            return this.key;
        }
    };
    return obj;
}

// This has PHP-style syntax
<?php
function php_function($param) {
    echo "This is PHP-like syntax";
    return $param;
}
?>