// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

/**
 * Complex Solidity program demonstrating advanced language features
 * for parser robustness testing
 */

// Import example (would typically import from external files)
import "./Interfaces.sol";
import "./Libraries.sol";

// Library definition
library MathUtils {
    // Type for fixed-point arithmetic (18 decimal places)
    type UFixed18 is uint256;
    
    // Function to create a UFixed18 from a uint
    function fromUint(uint256 value) internal pure returns (UFixed18) {
        return UFixed18.wrap(value * 1e18);
    }
    
    // Function to convert UFixed18 to uint
    function toUint(UFixed18 value) internal pure returns (uint256) {
        return UFixed18.unwrap(value) / 1e18;
    }
    
    // Complex math function
    function sqrt(uint256 x) internal pure returns (uint256) {
        if (x == 0) return 0;
        
        uint256 z = (x + 1) / 2;
        uint256 y = x;
        
        while (z < y) {
            y = z;
            z = (x / z + z) / 2;
        }
        
        return y;
    }
    
    function incomplete(uint x    {
        if (x < 
        
        
    
    // Function using internal types
    function calculateCompoundInterest(
        uint256 principal,
        uint256 rate,
        uint256 time,
        uint256 compoundingsPerYear
    ) internal pure returns (uint256) {
        // Convert to 18 decimal fixed-point
        UFixed18 principalFixed = fromUint(principal);
        UFixed18 rateFixed = UFixed18.wrap(rate); // Assumes rate is already scaled
        
        // Calculate (1 + rate/n)
        UFixed18 base = UFixed18.wrap(1e18 + UFixed18.unwrap(rateFixed) / compoundingsPerYear);
        
        // Calculate (1 + rate/n)^(n*t) - iterative approach for demonstration
        UFixed18 result = UFixed18.wrap(1e18); // Start with 1.0
        uint256 exponent = compoundingsPerYear * time;
        
        for (uint256 i = 0; i < exponent; i++) {
            result = UFixed18.wrap((UFixed18.unwrap(result) * UFixed18.unwrap(base)) / 1e18);
        }
        
        // Multiply by principal
        result = UFixed18.wrap((UFixed18.unwrap(principalFixed) * UFixed18.unwrap(result)) / 1e18);
        
        return toUint(result);
    }
}

// Interface definition
interface IToken {
    // Events
    event Transfer(address indexed from, address indexed to, uint256 value);
    event Approval(address indexed owner, address indexed spender, uint256 value);
    
    // Functions
    function totalSupply() external view returns (uint256);
    function balanceOf(address account) external view returns (uint256);
    function transfer(address to, uint256 value) external returns (bool);
    function allowance(address owner, address spender) external view returns (uint256);
    function approve(address spender, uint256 value) external returns (bool);
    function transferFrom(address from, address to, uint256 value) external returns (bool);
}

// Struct definitions
struct User {
    address account;
    string name;
    uint256 balance;
    bool active;
    uint256 lastActivity;
}

struct Proposal {
    uint256 id;
    string description;
    address proposer;
    uint256 forVotes;
    uint256 againstVotes;
    uint256 createdAt;
    uint256 endTime;
    bool executed;
    mapping(address => bool) hasVoted;
}

// Abstract contract
abstract contract AccessControl {
    // Role definition
    bytes32 public constant ADMIN_ROLE = keccak256("ADMIN_ROLE");
    bytes32 public constant OPERATOR_ROLE = keccak256("OPERATOR_ROLE");
    
    // Role membership
    mapping(bytes32 => mapping(address => bool)) private _roles;
    
    // Events
    event RoleGranted(bytes32 indexed role, address indexed account, address indexed sender);
    event RoleRevoked(bytes32 indexed role, address indexed account, address indexed sender);
    
    // Modifiers
    modifier onlyRole(bytes32 role) {
        require(hasRole(role, msg.sender), "AccessControl: sender doesn't have role");
        _;
    }
    
    // Functions
    function hasRole(bytes32 role, address account) public view returns (bool) {
        return _roles[role][account];
    }
    
    function grantRole(bytes32 role, address account) public virtual onlyRole(ADMIN_ROLE) {
        if (!hasRole(role, account)) {
            _roles[role][account] = true;
            emit RoleGranted(role, account, msg.sender);
        }
    }
    
    function revokeRole(bytes32 role, address account) public virtual onlyRole(ADMIN_ROLE) {
        if (hasRole(role, account)) {
            _roles[role][account] = false;
            emit RoleRevoked(role, account, msg.sender);
        }
    }
    
    // Function that must be implemented by inheriting contracts
    function initializeRoles(address admin) internal virtual;
}

// Custom errors (Solidity 0.8.4+)
error Unauthorized(address caller, bytes32 requiredRole);
error InvalidAmount(uint256 amount, string reason);
error TransferFailed(address from, address to, uint256 amount);
error DeadlineExpired(uint256 deadline, uint256 currentTime);

// Base ERC20 implementation
contract Token is IToken, AccessControl {
    // State variables
    string private _name;
    string private _symbol;
    uint8 private _decimals;
    uint256 private _totalSupply;
    
    // Token balances and allowances
    mapping(address => uint256) private _balances;
    mapping(address => mapping(address => uint256)) private _allowances;
    
    // Address set to track token holders
    mapping(address => bool) private _holders;
    address[] private _holdersList;
    
    // Constructor
    constructor(string memory name_, string memory symbol_, uint8 decimals_) {
        _name = name_;
        _symbol = symbol_;
        _decimals = decimals_;
        
        initializeRoles(msg.sender);
    }
    
    // Override from AccessControl
    function initializeRoles(address admin) internal override {
        _roles[ADMIN_ROLE][admin] = true;
        _roles[OPERATOR_ROLE][admin] = true;
        emit RoleGranted(ADMIN_ROLE, admin, address(0));
        emit RoleGranted(OPERATOR_ROLE, admin, address(0));
    }
    
    // Public view functions
    function name() public view returns (string memory) {
        return _name;
    }
    
    function symbol() public view returns (string memory) {
        return _symbol;
    }
    
    function decimals() public view returns (uint8) {
        return _decimals;
    }
    
    function totalSupply() public view override returns (uint256) {
        return _totalSupply;
    }
    
    function balanceOf(address account) public view override returns (uint256) {
        return _balances[account];
    }
    
    function allowance(address owner, address spender) public view override returns (uint256) {
        return _allowances[owner][spender];
    }
    
    // Holder management
    function getHoldersCount() public view returns (uint256) {
        return _holdersList.length;
    }
    
    function getHolderAtIndex(uint256 index) public view returns (address) {
        require(index < _holdersList.length, "Token: index out of bounds");
        return _holdersList[index];
    }
    
    // Public mutative functions
    function transfer(address to, uint256 value) public override returns (bool) {
        _transfer(msg.sender, to, value);
        return true;
    }
    
    function approve(address spender, uint256 value) public override returns (bool) {
        _approve(msg.sender, spender, value);
        return true;
    }
    
    function transferFrom(address from, address to, uint256 value) public override returns (bool) {
        uint256 currentAllowance = _allowances[from][msg.sender];
        
        if (currentAllowance != type(uint256).max) {
            require(currentAllowance >= value, "Token: insufficient allowance");
            _approve(from, msg.sender, currentAllowance - value);
        }
        
        _transfer(from, to, value);
        return true;
    }
    
    // Increase/decrease allowance with safety checks
    function increaseAllowance(address spender, uint256 addedValue) public returns (bool) {
        uint256 currentAllowance = _allowances[msg.sender][spender];
        require(currentAllowance + addedValue >= currentAllowance, "Token: allowance overflow");
        
        _approve(msg.sender, spender, currentAllowance + addedValue);
        return true;
    }
    
    function decreaseAllowance(address spender, uint256 subtractedValue) public returns (bool) {
        uint256 currentAllowance = _allowances[msg.sender][spender];
        require(currentAllowance >= subtractedValue, "Token: decreased allowance below zero");
        
        _approve(msg.sender, spender, currentAllowance - subtractedValue);
        return true;
    }
    
    // Admin functions
    function mint(address account, uint256 amount) public onlyRole(OPERATOR_ROLE) {
        require(account != address(0), "Token: mint to the zero address");
        
        _totalSupply += amount;
        _balances[account] += amount;
        
        _addHolder(account);
        
        emit Transfer(address(0), account, amount);
    }
    
    function burn(address account, uint256 amount) public onlyRole(OPERATOR_ROLE) {
        require(account != address(0), "Token: burn from the zero address");
        uint256 accountBalance = _balances[account];
        require(accountBalance >= amount, "Token: burn amount exceeds balance");
        
        _balances[account] = accountBalance - amount;
        _totalSupply -= amount;
        
        if (_balances[account] == 0) {
            _removeHolder(account);
        }
        
        emit Transfer(account, address(0), amount);
    }
    
    // Internal functions
    function _transfer(address from, address to, uint256 amount) internal virtual {
        require(from != address(0), "Token: transfer from the zero address");
        require(to != address(0), "Token: transfer to the zero address");
        
        uint256 fromBalance = _balances[from];
        require(fromBalance >= amount, "Token: transfer amount exceeds balance");
        
        _balances[from] = fromBalance - amount;
        _balances[to] += amount;
        
        if (fromBalance == amount) {
            _removeHolder(from);
        }
        
        _addHolder(to);
        
        emit Transfer(from, to, amount);
    }
    
    function _approve(address owner, address spender, uint256 amount) internal virtual {
        require(owner != address(0), "Token: approve from the zero address");
        require(spender != address(0), "Token: approve to the zero address");
        
        _allowances[owner][spender] = amount;
        emit Approval(owner, spender, amount);
    }
    
    function _addHolder(address account) internal {
        if (!_holders[account] && _balances[account] > 0) {
            _holders[account] = true;
            _holdersList.push(account);
        }
    }
    
    function _removeHolder(address account) internal {
        if (_holders[account] && _balances[account] == 0) {
            _holders[account] = false;
            
            // Find and remove from the list (gas-intensive, could be optimized)
            for (uint256 i = 0; i < _holdersList.length; i++) {
                if (_holdersList[i] == account) {
                    // Swap with the last element and pop
                    _holdersList[i] = _holdersList[_holdersList.length - 1];
                    _holdersList.pop();
                    break;
                }
            }
        }
    }
}

// Governance contract with complex logic
contract Governance {
    // State variables
    Token public token;
    uint256 public proposalCount;
    uint256 public minVotingPower;
    uint256 public votingPeriod;
    
    // Proposals mapping
    mapping(uint256 => Proposal) public proposals;
    
    // Events
    event ProposalCreated(uint256 indexed id, address indexed proposer, string description, uint256 endTime);
    event VoteCast(uint256 indexed proposalId, address indexed voter, bool support, uint256 weight);
    event ProposalExecuted(uint256 indexed id);
    
    // Constructor
    constructor(address tokenAddress, uint256 _minVotingPower, uint256 _votingPeriod) {
        token = Token(tokenAddress);
        minVotingPower = _minVotingPower;
        votingPeriod = _votingPeriod;
    }
    
    // Modifiers
    modifier onlyTokenHolder() {
        require(token.balanceOf(msg.sender) > 0, "Governance: caller is not a token holder");
        _;
    }
    
    // Create a new proposal
    function createProposal(string calldata description) external onlyTokenHolder returns (uint256) {
        require(token.balanceOf(msg.sender) >= minVotingPower, "Governance: insufficient voting power");
        
        uint256 proposalId = ++proposalCount;
        Proposal storage newProposal = proposals[proposalId];
        
        newProposal.id = proposalId;
        newProposal.description = description;
        newProposal.proposer = msg.sender;
        newProposal.createdAt = block.timestamp;
        newProposal.endTime = block.timestamp + votingPeriod;
        
        emit ProposalCreated(proposalId, msg.sender, description, newProposal.endTime);
        
        return proposalId;
    }
    
    // Cast a vote on a proposal
    function castVote(uint256 proposalId, bool support) external onlyTokenHolder {
        Proposal storage proposal = proposals[proposalId];
        
        require(proposal.id == proposalId, "Governance: proposal does not exist");
        require(block.timestamp <= proposal.endTime, "Governance: voting period ended");
        require(!proposal.hasVoted[msg.sender], "Governance: already voted");
        
        uint256 votingPower = token.balanceOf(msg.sender);
        
        if (support) {
            proposal.forVotes += votingPower;
        } else {
            proposal.againstVotes += votingPower;
        }
        
        proposal.hasVoted[msg.sender] = true;
        
        emit VoteCast(proposalId, msg.sender, support, votingPower);
    }
    
    // Execute a proposal after voting period
    function executeProposal(uint256 proposalId) external {
        Proposal storage proposal = proposals[proposalId];
        
        require(proposal.id == proposalId, "Governance: proposal does not exist");
        require(block.timestamp > proposal.endTime, "Governance: voting period not ended");
        require(!proposal.executed, "Governance: proposal already executed");
        require(proposal.forVotes > proposal.againstVotes, "Governance: proposal did not pass");
        
        proposal.executed = true;
        
        // Execute proposal logic here
        // This would typically involve calling functions on other contracts
        
        emit ProposalExecuted(proposalId);
    }
    
    // View function to check proposal details
    function getProposalDetails(uint256 proposalId) external view returns (
        uint256 id,
        string memory description,
        address proposer,
        uint256 forVotes,
        uint256 againstVotes,
        uint256 createdAt,
        uint256 endTime,
        bool executed
    ) {
        Proposal storage proposal = proposals[proposalId];
        require(proposal.id == proposalId, "Governance: proposal does not exist");
        
        return (
            proposal.id,
            proposal.description,
            proposal.proposer,
            proposal.forVotes,
            proposal.againstVotes,
            proposal.createdAt,
            proposal.endTime,
            proposal.executed
        );
    }
    
    // Check if an address has voted on a proposal
    function hasVoted(uint256 proposalId, address voter) external view returns (bool) {
        Proposal storage proposal = proposals[proposalId];
        require(proposal.id == proposalId, "Governance: proposal does not exist");
        
        return proposal.hasVoted[voter];
    }
    
    // Calculate voting power distribution
    function getVotingDistribution(uint256 proposalId) external view returns (
        uint256 totalVotes,
        uint256 forPercentage,
        uint256 againstPercentage
    ) {
        Proposal storage proposal = proposals[proposalId];
        require(proposal.id == proposalId, "Governance: proposal does not exist");
        
        totalVotes = proposal.forVotes + proposal.againstVotes;
        
        if (totalVotes == 0) {
            return (0, 0, 0);
        }
        
        // Calculate percentages with 2 decimal places precision
        forPercentage = (proposal.forVotes * 10000) / totalVotes;
        againstPercentage = (proposal.againstVotes * 10000) / totalVotes;
        
        return (totalVotes, forPercentage, againstPercentage);
    }
    
    // Function using library
    function calculateVotingPower(uint256 initialPower, uint256 timeHeld) external pure returns (uint256) {
        // Compound interest calculation as a simplified vesting boost
        // 5% APY with quarterly compounding
        return MathUtils.calculateCompoundInterest(
            initialPower,
            5 * 1e16, // 5% represented as fixed point
            timeHeld / 365 days, // Convert to years
            4 // Quarterly compounding
        );
    }
    
    // Try-catch example (Solidity 0.6.0+)
    function safeExecuteProposal(uint256 proposalId) external returns (bool success, string memory errorMessage) {
        try this.executeProposal(proposalId) {
            return (true, "");
        } catch Error(string memory reason) {
            // Revert with reason
            return (false, reason);
        } catch (bytes memory /*lowLevelData*/) {
            // Low-level error without reason
            return (false, "Unknown error occurred");
        }
    }
    
    // Function with complex return types
    function getProposalStats(uint256 startId, uint256 endId) external view returns (
        uint256[] memory ids,
        address[] memory proposers,
        uint256[] memory voteCounts,
        bool[] memory executed
    ) {
        require(startId <= endId && endId <= proposalCount, "Governance: invalid range");
        
        uint256 count = endId - startId + 1;
        ids = new uint256[](count);
        proposers = new address[](count);
        voteCounts = new uint256[](count);
        executed = new bool[](count);
        
        for (uint256 i = 0; i < count; i++) {
            uint256 proposalId = startId + i;
            Proposal storage proposal = proposals[proposalId];
            
            ids[i] = proposalId;
            proposers[i] = proposal.proposer;
            voteCounts[i] = proposal.forVotes + proposal.againstVotes;
            executed[i] = proposal.executed;
        }
        
        return (ids, proposers, voteCounts, executed);
    }
    
    // Function with assembly block
    function addressToUint(address addr) public pure returns (uint256) {
        uint256 result;
        
        assembly {
            result := addr
        }
        
        return result;
    }
    
    // Receive function
    receive() external payable {
        // Handle direct ETH transfers
    }
    
    // Fallback function
    fallback() external payable {
        // Handle unknown function calls
        revert("Governance: function not found");
    }
}

// Factory contract to deploy new token instances
contract TokenFactory {
    // Events
    event TokenCreated(address indexed tokenAddress, string name, string symbol, address creator);
    
    // Array to track created tokens
    address[] public createdTokens;
    
    // Create a new token
    function createToken(string calldata name, string calldata symbol, uint8 decimals) external returns (address) {
        Token newToken = new Token(name, symbol, decimals);
        
        address tokenAddress = address(newToken);
        createdTokens.push(tokenAddress);
        
        emit TokenCreated(tokenAddress, name, symbol, msg.sender);
        
        return tokenAddress;
    }
    
    // Get count of created tokens
    function getTokenCount() external view returns (uint256) {
        return createdTokens.length;
    }
    
    // Get multiple tokens at once
    function getTokenBatch(uint256 start, uint256 count) external view returns (address[] memory tokens) {
        require(start + count <= createdTokens.length, "TokenFactory: range out of bounds");
        
        tokens = new address[](count);
        
        for (uint256 i = 0; i < count; i++) {
            tokens[i] = createdTokens[start + i];
        }
        
        return tokens;
    }
}
