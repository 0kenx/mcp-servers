import React from 'react';

function globalFunc() {
    return true;
}

class GlobalClass {
    method() {
        return this;
    }
}

const CONSTANT = 42;