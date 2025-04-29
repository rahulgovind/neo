/**
 * Utility functions for handling markdown content
 */

// Import a markdown parser like marked.js or showdown
// For now, using a simplified implementation that handles basic markdown

/**
 * Processes markdown content to HTML
 */
export function processMarkdown(content: string): string {
  if (!content) return '';
  
  // Preserve newlines and whitespace by converting them to HTML entities
  // This will help maintain formatting in the final output
  content = _preserveWhitespace(content);
  
  // Process code blocks
  content = _processCodeBlocks(content);
  
  // Process inline code
  content = _processInlineCode(content);
  
  // Process bold text
  content = _processBoldText(content);
  
  // Process italics
  content = _processItalics(content);
  
  // Process links
  content = _processLinks(content);
  
  // Process lists
  content = _processLists(content);
  
  // Process paragraphs
  content = _processParagraphs(content);
  
  return content;
}

/**
 * Process code blocks with syntax highlighting
 */
function _processCodeBlocks(text: string): string {
  return text.replace(/```(\w+)?\n([\s\S]*?)\n```/g, (match, lang, code) => {
    const language = lang || '';
    const escapedCode = _escapeHtml(code);
    return `<pre><code class="language-${language}">${escapedCode}</code></pre>`;
  });
}

/**
 * Process inline code spans
 */
function _processInlineCode(text: string): string {
  return text.replace(/`([^`]+)`/g, '<code>$1</code>');
}

/**
 * Process bold text
 */
function _processBoldText(text: string): string {
  return text.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
            .replace(/__([^_]+)__/g, '<strong>$1</strong>');
}

/**
 * Process italic text
 */
function _processItalics(text: string): string {
  return text.replace(/\*([^*]+)\*/g, '<em>$1</em>')
            .replace(/_([^_]+)_/g, '<em>$1</em>');
}

/**
 * Process links
 */
function _processLinks(text: string): string {
  return text.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
}

/**
 * Process unordered and ordered lists
 */
function _processLists(text: string): string {
  // Handle unordered lists
  text = text.replace(/(?:^|\n)((?:\* [^\n]+\n?)+)/g, (match, listContent) => {
    const items = listContent.split('\n')
      .filter((item: string) => item.startsWith('* '))
      .map((item: string) => `<li>${item.substring(2)}</li>`)
      .join('');
    return `\n<ul>${items}</ul>\n`;
  });
  
  // Handle ordered lists
  text = text.replace(/(?:^|\n)((?:\d+\. [^\n]+\n?)+)/g, (match, listContent) => {
    const items = listContent.split('\n')
      .filter((item: string) => /^\d+\. /.test(item))
      .map((item: string) => `<li>${item.replace(/^\d+\. /, '')}</li>`)
      .join('');
    return `\n<ol>${items}</ol>\n`;
  });
  
  return text;
}

/**
 * Process paragraphs, respecting pre-existing formatting
 */
function _processParagraphs(text: string): string {
  // Skip wrapping paragraphs for content already containing HTML tags
  if (/<\/?[a-z][\s\S]*>/i.test(text)) {
    return text;
  }
  
  // Identify paragraphs (text between consecutive <br> tags)
  // We're more careful here to not disrupt the <br> tags we've inserted for newlines
  const paragraphs = text.split(/<br><br>+/);
  
  return paragraphs.map(para => {
    if (para.trim() && !para.trim().startsWith('<')) {
      return `<p>${para}</p>`;
    }
    return para;
  }).join('<br><br>');
}

/**
 * Escape HTML to prevent XSS
 */
function _escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

/**
 * Preserve whitespace and line breaks in markdown content
 * Converts spaces and newlines to appropriate HTML to maintain original formatting
 */
function _preserveWhitespace(text: string): string {
  // First, preserve consecutive newlines by converting them to <br> tags
  // This ensures multiple newlines don't get collapsed
  text = text.replace(/\n{2,}/g, match => {
    // For each newline, add a <br>
    return '<br>'.repeat(match.length);
  });
  
  // Then handle single newlines (not preceded or followed by another newline)
  text = text.replace(/([^\n])\n([^\n])/g, '$1<br>$2');
  
  // Handle multiple consecutive spaces (but not inside code blocks or HTML tags)
  let result = '';
  let inTag = false;
  let inCodeBlock = false;
  
  // Process text character by character to handle spaces properly
  for (let i = 0; i < text.length; i++) {
    const char = text[i];
    const nextChar = text[i + 1];
    
    if (char === '<') inTag = true;
    if (char === '>') inTag = false;
    if (char === '`' && text.slice(i, i + 3) === '```') inCodeBlock = !inCodeBlock;
    
    // Only convert spaces outside tags and code blocks
    if (char === ' ' && nextChar === ' ' && !inTag && !inCodeBlock) {
      result += '&nbsp;';
    } else {
      result += char;
    }
  }
  
  return result;
}

/**
 * Process command displays
 */
export function processCommands(content: string): string {
  // Match command display patterns
  return content.replace(/▶([^｜]+)｜([^■]+)■\n[✅❌]([^■]+)■/g, (match, command, description, result) => {
    return `<div class="command-block p-2 mb-2 bg-gray-800 rounded">
              <div class="command-line text-sm">
                <span class="text-green-500">▶</span> <span class="text-blue-400">${_escapeHtml(command.trim())}</span>
                <span class="text-gray-400">｜${_escapeHtml(description.trim())}</span>
              </div>
              <div class="command-result text-sm mt-1 pl-2 border-l-2 border-gray-600">
                ${result.startsWith('✅') ? 
                  `<span class="text-green-500">✅</span> ${_escapeHtml(result.substring(1).trim())}` : 
                  `<span class="text-red-500">❌</span> ${_escapeHtml(result.substring(1).trim())}`}
              </div>
            </div>`;
  });
}
