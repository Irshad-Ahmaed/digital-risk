class AppException(Exception):
    status_code: int = 500
    error_code: str = "INTERNAL_ERROR"
    message: str = "An unexpected error occurred"

    def __init__(self, message: str = None):
        self.message = message if message is not None else self.__class__.message
        super().__init__(self.message)


class TransactionConflictError(AppException):
    """Same transaction_id reused with DIFFERENT payload → 409"""
    status_code = 409
    error_code = "TRANSACTION_CONFLICT"
    message = "Transaction ID already used with different parameters"


class InsufficientFundsError(AppException):
    status_code = 422
    error_code = "INSUFFICIENT_FUNDS"
    message = "Insufficient funds for this transaction"

    def __init__(self, balance: int, amount: int):
        msg = f"Balance {balance} cents is insufficient for debit of {amount} cents"
        super().__init__(msg)


class UserNotFoundError(AppException):
    status_code = 404
    error_code = "USER_NOT_FOUND"
    message = "User not found"


class RateLimitExceededError(AppException):
    status_code = 429
    error_code = "RATE_LIMIT_EXCEEDED"
    message = "Too many transactions. Max 10 per minute allowed."
