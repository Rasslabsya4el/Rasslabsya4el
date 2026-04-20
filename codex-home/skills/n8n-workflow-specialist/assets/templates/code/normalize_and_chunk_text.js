const source =
  $json.body?.text ??
  $json.text ??
  '';

const documentId =
  $json.body?.document_id ??
  $json.document_id ??
  'unknown-doc';

const title =
  $json.body?.title ??
  $json.title ??
  'Untitled';

const normalized = source.replace(/\s+/g, ' ').trim();
const chunkSize = 600;
const overlap = 100;
const step = Math.max(1, chunkSize - overlap);
const maxChunks = 8;

const itemsOut = [];

for (let start = 0, chunkIndex = 0; start < normalized.length && chunkIndex < maxChunks; start += step, chunkIndex++) {
  const chunkText = normalized.slice(start, start + chunkSize).trim();
  if (!chunkText) continue;

  itemsOut.push({
    json: {
      document_id: documentId,
      title,
      chunk_index: chunkIndex,
      chunk_text: chunkText,
      created_at: new Date().toISOString()
    }
  });
}

return itemsOut;
