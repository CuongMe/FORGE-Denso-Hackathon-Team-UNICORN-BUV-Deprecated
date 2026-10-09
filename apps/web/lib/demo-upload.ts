export function getDemoUploadStages(file: Pick<File, 'name' | 'type'>) {
  const isImage = file.type.startsWith('image/') || /\.(png|jpe?g|bmp|webp)$/iu.test(file.name);
  return isImage
    ? ['uploading', 'parsing', 'ocr', 'vlm_analysis', 'chunking', 'embedding', 'indexing', 'completed']
    : ['uploading', 'parsing', 'ocr', 'table_extraction', 'chunking', 'embedding', 'indexing', 'completed'];
}
