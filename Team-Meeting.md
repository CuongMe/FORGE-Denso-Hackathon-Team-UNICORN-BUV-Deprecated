kế hoạch triển khai gantt chart.

thông tin trên timeline sẽ có những phần nào.

data curation hoàn thiện phần thu thập dữ liệu cho sản phẩm
front end design hoàn thiện phần front end cho sản phẩm.
back-end design and implementation.
pilot bản demo trên cloud để denso engineer đánh giá trước khi đưa vào tích hợp DensoGPT và vận hành.



Sửa Font cho UI - Team Discussion

Thêm truy xuất raw file cho bảng hybrid rerank

Đặt câu hỏi qua các file. Aggregate câu trả lời.

Slide metrics làm rõ ngữ cảnh


1. Trình bày điểm mới, đột phá so với các giải pháp truyền thống?
Trích dẫn nguồn AI Xử lý chuyên sâu cho nhà máy: Giải pháp được Fine-tuned và kiểm soát nghiêm ngặt bởi đội ngũ kỹ sư trong nhà máy, mang lại kết quả chính xác cao và tập trung tốt hơn cho môi trường công nghiệp thay vì sử dụng các dịch vụ cloud docs chung chung (như Azure hay AWS).

Kiến trúc Local-First tối ưu chi phí: Thiết kế theo hướng ưu tiên cục bộ (local-first), giúp giải pháp lưu trữ dữ liệu an toàn, có khả năng chịu lỗi tốt với mức chi phí tiết kiệm, gần bằng các giải pháp truyền thống nhưng vượt trội về tính bảo mật.

Trích dẫn nguồn AI tin cậy & Đa phương thức: Kết hợp khả năng xử lý tài liệu đa phương thức, tích hợp DensoGPT và quy trình RAG an toàn đi kèm hệ thống trích dẫn nguồn gốc rõ ràng từ thông tin đã được chắt lọc, kiểm định.
2. Ý tưởng này đang giải quyết vấn đề gì tại Denso?
Xử lý phân mảnh tài liệu đa định dạng: Giải quyết tình trạng tài liệu nằm rải rác ở nhiều định dạng khác nhau (như PDF, hình ảnh, tệp Excel) và đặc biệt là các tài liệu song ngữ Việt – Nhật, giúp loại bỏ việc tìm kiếm thủ công kém hiệu quả.
Tự động hóa xây dựng nguồn dữ liệu tri thức: Tự động hóa quy trình xử lý dữ liệu và tài liệu phân tán qua các phòng ban tại Denso, từ đó tạo ra nguồn RAG, cơ sở dữ liệu và vector database chất lượng cao phục vụ cho hệ thống AI.
Thúc đẩy tầm nhìn tự động hóa: Đặt nền móng hướng tới mục tiêu tự động hóa toàn diện cho nhà máy vận hành theo phương thức cục bộ (local-first factory) vào năm 2030.
3. Phương pháp/công cụ áp dụng và thời gian thực hiện dự án?
Tech Stack ưu tiên cục bộ (Local-First): Sử dụng kiến trúc hiện đại và khép kín bao gồm Next.js (Giao diện), FastAPI (Backend), Docling & Florence-2 (Xử lý tài liệu đa phương thức và trích xuất hình ảnh/văn bản), BGE-M3 (Tạo embedding đa ngôn ngữ), Qdrant (Vector database) và bge-reranker-v2-m3 (Tối ưu kết quả tìm kiếm).
Thời gian thực hiện: Lộ trình chi tiết và tiến độ triển khai đã được hoạch định cụ thể theo sơ đồ Gantt Chart của dự án.
4. Ý tưởng này mang lại hiệu quả gì? Cho số liệu.
Tối ưu chi phí và bảo mật tuyệt đối: Giải pháp vận hành theo mô hình cục bộ (localhost 0 đồng), mang lại hệ thống chạy nhanh, ổn định, mạnh mẽ, đảm bảo tính riêng tư và bảo mật tuyệt đối (private, privacy).
Nâng cao năng suất và hiệu quả công việc: Giúp giảm thiểu thời gian tìm kiếm tài liệu, cải thiện khả năng tiếp cận thông tin và cắt giảm đáng kể khối lượng công việc thủ công của nhân sự trong nhà máy.
Số liệu đột phá: Rút ngắn thời gian xử lý và tìm kiếm dữ liệu thủ công từ 60 phút xuống còn dưới 3 phút.
5.  Khả năng mở rộng, triển khai ngang của dự án là gì (trong nội bộ Denso hoặc các nhà máy khác)?
Khả năng: Thử nghiệm tecch stacks trên nhà máy Việt Nam --> áp dụng cho thị trường của nhà máy Nhật (chi phí rủi ro việt nam thấp --> giảm thiểu được tối đa chi phí áp dụng cho các thị trường nhà máy nhật hay các nước phastr triển khi có rủi ro về hỏng hóc)
6. Nhóm đã có những kiến thức hoặc kinh nghiệm nào giúp thực hiện giải pháp?
Sinh viên có kinh nghiệm và học các chuyên nghành chuyên môn liên quan tới Data Science and AI và Software Engineering

FORGE sẽ là pilot RAG ENGINE được thử nghiệm trên nhà máy Denso Vietnam. FORGE được design offline first. làm cho techstack này có thể reproducible và apply cho các nhà máy Nhật hoặc bất kỳ nhà máy nào ưu tiên 1 tech stack offline, local, automate.
