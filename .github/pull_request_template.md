# Pull Request

<!--
  Pull Request Template
  =====================
  Provide a high-quality, concise description of your changes.
  PRs that follow this template are easier to review and merge.
  
  For more information about contributing, see docs/CONTRIBUTING.md
-->

## 📄 Description

<!-- What does this PR change? Why is it needed? -->

## ✅ Checklist

### Code Quality

- [ ] I ran `pixi run lint` and all checks pass
- [ ] Code follows existing conventions and style guidelines
- [ ] Commit messages are clear and descriptive

### Testing

- [ ] I ran `pixi run test` and all tests pass
- [ ] Tests added/updated for new functionality
- [ ] Performance-critical features include benchmarks (`pixi run benchmark`)

### Documentation

- [ ] Documentation updated for API changes
- [ ] Docstrings added for new functions and classes
- [ ] Examples included for new features
- [ ] I have linked the issue this PR closes (if any)

## 🔗 Related Issues

Resolves #\<issue-number>

## 💡 Type of change

| Type                          | Checked? |
|-------------------------------|----------|
| 🐞 Bug fix                   | [ ]      |
| ✨ New feature               | [ ]      |
| 📝 Documentation             | [ ]      |
| ♻️ Refactor                  | [ ]      |
| 🛠️ Build/CI                  | [ ]      |
| 🚀 Performance improvement   | [ ]      |
| 🔧 HPX C++ binding update    | [ ]      |
| 🧵 Free-threading related    | [ ]      |
| 🧪 Testing infrastructure    | [ ]      |
| Other (explain below)        | [ ]      |

## 🧪 How to test

<!-- 
Steps reviewers can run to verify functionality.
Please include specific commands using pixi tasks when applicable:
- `pixi run test` - Run the full test suite
- `pixi run benchmark` - Run performance benchmarks  
- `pixi run lint` - Check code quality
- `pixi shell -e py313` - Activate development environment
-->

## 🏗️ Build and Environment

- [ ] Changes work with Python 3.13 free-threading (`py313t` environment)
- [ ] Changes work with standard Python 3.13 (`py313` environment)
- [ ] No issues with HPX C++ library integration
- [ ] Cross-platform compatibility considered (Linux/macOS/Windows)

## 📝 Notes to reviewers

<!-- 
Anything specific reviewers should know before starting.
Include information about:
- Complex implementation details
- Performance implications
- Breaking changes
- Dependencies on other PRs
-->