module.exports = {
  '/api/**': {
    target: `http://127.0.0.1:${process.env.PAPERLAB_API_PORT || 8000}`,
    secure: false,
    pathRewrite: { '^/api': '' },
  },
};
