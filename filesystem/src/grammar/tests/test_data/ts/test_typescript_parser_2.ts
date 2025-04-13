/**
 * ID type.
 */
type ID = string | number;

// Generic type
type Result<T> = {
    success: boolean;
    data?: T;
    error?: string;
};