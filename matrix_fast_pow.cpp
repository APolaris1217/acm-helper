#include <iostream>
#include <vector>

using namespace std;

typedef long long ll;
typedef vector<vector<ll>> Matrix;

const ll MOD = 1e9 + 7;

Matrix multiply(const Matrix &A, const Matrix &B, int n) {
    Matrix C(n, vector<ll>(n, 0));
    for (int i = 0; i < n; ++i)
        for (int k = 0; k < n; ++k)
            if (A[i][k])
                for (int j = 0; j < n; ++j)
                    C[i][j] = (C[i][j] + A[i][k] * B[k][j]) % MOD;
    return C;
}

Matrix identity(int n) {
    Matrix I(n, vector<ll>(n, 0));
    for (int i = 0; i < n; ++i)
        I[i][i] = 1;
    return I;
}

Matrix pow(Matrix A, ll exp, int n) {
    Matrix result = identity(n);
    while (exp) {
        if (exp & 1)
            result = multiply(result, A, n);
        A = multiply(A, A, n);
        exp >>= 1;
    }
    return result;
}

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    int n;
    ll exp;
    cin >> n >> exp;

    Matrix mat(n, vector<ll>(n));
    for (int i = 0; i < n; ++i)
        for (int j = 0; j < n; ++j)
            cin >> mat[i][j];

    Matrix result = pow(mat, exp, n);

    for (int i = 0; i < n; ++i) {
        for (int j = 0; j < n; ++j)
            cout << result[i][j] << " \n"[j == n - 1];
    }

    return 0;
}
