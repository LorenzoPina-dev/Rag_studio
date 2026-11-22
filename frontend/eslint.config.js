import js from '@eslint/js'
import tseslint from 'typescript-eslint'

/**
 * Flat ESLint config. TypeScript already checks types and unused symbols via
 * `tsc -b`, so ESLint focuses on correctness rules that complement it.
 */
export default tseslint.config(
  { ignores: ['dist/**', 'node_modules/**', 'coverage/**'] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: ['**/*.{ts,tsx}'],
    rules: {
      // TypeScript owns these checks (tsconfig has noUnusedLocals disabled too).
      'no-undef': 'off',
      'no-unused-vars': 'off',
      '@typescript-eslint/no-unused-vars': 'off',
      '@typescript-eslint/no-explicit-any': 'off',
      '@typescript-eslint/no-empty-object-type': 'off',
      '@typescript-eslint/no-require-imports': 'off',
      'no-empty': 'off',
      'no-case-declarations': 'off',
      'no-useless-escape': 'off',
      'no-control-regex': 'off',
    },
  },
  {
    files: ['**/*.js', '**/*.cjs'],
    rules: {
      'no-undef': 'off',
    },
  },
)
