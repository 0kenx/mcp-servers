// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

/**
 * A simple Solidity contract demonstrating language features
 * with some edge cases for parser testing
 */

contract SimpleStorage {
    // State variables
    uint256 private value;
    address public owner;
    bool public initialized;
    string public name;
    
    // Events
    event ValueChanged(uint256 oldValue, uint256 newValue);
    event OwnershipTransferred(address indexed previousOwner, address indexed newOwner);
    
    // Constructor
    constructor(string memory _name) {
        owner = msg.sender;
        name = _name;
        initialized = true;
    }
    
    // Modifiers
    modifier onlyOwner() {
        require(msg.sender == owner, "Not the owner");
        _;
    }
    
    modifier whenInitialized() {
        require(initialized, "Not initialized");
        _;
    }
    
    // External function
    function setValue(uint256 _value) external onlyOwner whenInitialized {
        emit ValueChanged(value, _value);
        value = _value;
    }
    
    // Public function with return value
    function getValue() public view returns (uint256) {
        return value;
    }
    
    // Internal function
    function _transferOwnership(address newOwner) internal {
        require(newOwner != address(0), "New owner is the zero address");
        emit OwnershipTransferred(owner, newOwner);
        owner = newOwner;
    }
    
    // Function with error handling
    function transferOwnership(address newOwner) public onlyOwner {
        _transferOwnership(newOwner);
    }
    
    // Function with multiple parameters and return values
    function calculate(uint256 a, uint256 b) public pure returns (uint256 sum, uint256 product) {
        sum = a + b;
        product = a * b;
    }
}
