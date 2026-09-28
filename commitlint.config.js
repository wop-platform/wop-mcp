/**
 * commitlint 配置 —— 对齐 wop-skills 治理标准与 Conventional Commits
 * 规则等级：2 = error（阻断）| 1 = warn（警告不阻断）| 0 = 关闭
 */
module.exports = {
  extends: ['@commitlint/config-conventional'],
  rules: {
    'type-enum': [
      2,
      'always',
      ['feat', 'fix', 'docs', 'style', 'refactor', 'perf', 'test', 'chore', 'revert'],
    ],
    'scope-enum': [
      1,
      'always',
      ['api', 'docs', 'keypair', 'mcp', 'http', 'crypto', 'ci', 'build', 'test', 'security', 'deps'],
    ],
    'subject-max-length': [2, 'always', 50],
    'header-max-length': [2, 'always', 72],
    // 中文 subject 不适用英文大小写规则
    'subject-case': [0],
  },
};
