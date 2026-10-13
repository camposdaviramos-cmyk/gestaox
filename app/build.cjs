const fs = require('fs');
const babel = require('./web/vendor/babel.min.js');
const result = babel.transform(fs.readFileSync('web/app.jsx', 'utf8'), {presets: ['react'], comments: false, compact: true});
fs.writeFileSync('web/app.js', result.code);
console.log('React compilado: web/app.js');
