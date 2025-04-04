import { Component } from '@angular/core';

interface User {
    id: number;
    name: string;
}

type ID = number;

enum Status {
    Active,
    Inactive
}

const API_URL = 'https://api.example.com';

class UserService {
    getUsers(): User[] {
        return [];
    }
}

function formatUser(user: User): string {
    return user.name;
}

export default UserService;