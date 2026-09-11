export function highlightHtml(text: string, filename: string): string {
  const ext = filename.split('.').pop()?.toLowerCase();

  if (ext === 'md') {
    let html = text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

    // 1. Headings (Dracula Pallete)
    html = html.replace(
      /^(#\s.+)$/gm,
      '<span style="color: #ff79c6; font-weight: bold;">$1</span>',
    );
    html = html.replace(
      /^(##\s.+)$/gm,
      '<span style="color: #8be9fd; font-weight: bold;">$1</span>',
    );
    html = html.replace(
      /^(###\s.+)$/gm,
      '<span style="color: #50fa7b; font-weight: bold;">$1</span>',
    );

    // 2. Lists and Items
    html = html.replace(/^(\s*[-*+]\s)/gm, '<span style="color: #ffb86c;">$1</span>');
    html = html.replace(/^(\s*\d+\.\s)/gm, '<span style="color: #ffb86c;">$1</span>');

    // 3. Links [text](url)
    html = html.replace(/(\[[^\]]+\]\([^)]+\))/g, '<span style="color: #f1fa8c;">$1</span>');

    // 4. Bold and Italic
    html = html.replace(
      /(\*\*[^*]+\*\*)/g,
      '<span style="color: #ff79c6; font-weight: bold;">$1</span>',
    );
    html = html.replace(
      /(\*[^*]+\*)/g,
      '<span style="color: #f1fa8c; font-style: italic;">$1</span>',
    );

    // 5. Inline Code `code` - sem tarja, só cor
    html = html.replace(
      /`([^`]+)`/g,
      '<code style="color: #f1fa8c; font-family: monospace;">$1</code>',
    );

    // 6. Code Blocks ```python ... ``` - sem tarja, só cor
    html = html.replace(
      /(```[A-Za-z0-9]*\n[\s\S]*?\n```)/g,
      '<pre style="color: #bd93f9; font-family: monospace; display: block; margin: 10px 0;">$1</pre>',
    );

    // 7. Tables - clean and simple, no tarjas
    // 7a. Table divider lines (only |, -, :, and spaces)
    html = html.replace(
      /^[ \t]*[|][\s|:\-]*[-][\s|:\-]*[|][ \t]*$/gm,
      '<span style="color: #6272a4;">$&</span>',
    );
    // 7b. Pipe separators in tables (only the | character)
    html = html.replace(/\|/g, '<span style="color: #6272a4;">|</span>');

    return html.replace(/\n/g, '<br>');
  }

  // Default: plain text fallback for non-markdown files
  return text.replace(/\n/g, '<br>');
}
