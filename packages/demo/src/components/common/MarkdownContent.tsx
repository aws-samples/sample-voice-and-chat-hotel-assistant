/**
 * Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: MIT-0
 */

import { useEffect, useState } from 'react';
import { unified } from 'unified';
import remarkParse from 'remark-parse';
import remarkGfm from 'remark-gfm';
import remarkRehype from 'remark-rehype';
import rehypeStringify from 'rehype-stringify';
import rehypeSanitize from 'rehype-sanitize';

interface MarkdownContentProps {
  children: string;
}

export function MarkdownContent({ children }: MarkdownContentProps) {
  const [processedHtml, setProcessedHtml] = useState<string>('');

  useEffect(() => {
    async function processMarkdown() {
      try {
        const result = await unified()
          .use(remarkParse)
          .use(remarkGfm)
          .use(remarkRehype)
          .use(rehypeSanitize)
          .use(rehypeStringify)
          .process(children || '');

        setProcessedHtml(String(result));
      } catch (error) {
        console.error('Error processing markdown:', error);
      }
    }

    processMarkdown();
  }, [children]);

  return <div className="markdown-content" dangerouslySetInnerHTML={{ __html: processedHtml }} />;
}
