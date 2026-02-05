const http = require("http");
const fs = require("fs");
const path = require("path");

const port = Number(process.env.PORT || 3000);
const basePath = __dirname;

const mimeTypes = {
  ".html": "text/html",
  ".js": "text/javascript",
  ".css": "text/css",
  ".json": "application/json",
};

const serveFile = (filePath, response) => {
  fs.readFile(filePath, (err, content) => {
    if (err) {
      response.writeHead(404, { "Content-Type": "text/plain" });
      response.end("Not Found");
      return;
    }

    const ext = path.extname(filePath);
    response.writeHead(200, { "Content-Type": mimeTypes[ext] || "text/plain" });
    response.end(content);
  });
};

const server = http.createServer((request, response) => {
  const urlPath = request.url === "/" ? "/index.html" : request.url;
  const safePath = path.normalize(urlPath).replace(/^\.\.(\/|\\)/, "");
  const filePath = path.join(basePath, safePath);
  serveFile(filePath, response);
});

server.listen(port, () => {
  console.log(`Tyler trainer server running at http://localhost:${port}`);
});
