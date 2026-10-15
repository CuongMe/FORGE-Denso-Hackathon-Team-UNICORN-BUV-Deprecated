### BẮT ĐẦU — SLIDE 1 & 2 — NGƯỜI TRÌNH BÀY: Phan Tuấn Minh
Xin chào Ban giám khảo cùng các anh chị Mentor từ DENSO và FPT Software. Chúng em là đội UNICORN đến từ trường Đại học Anh Quốc Việt Nam (BUV). Hôm nay, chúng em mang đến giải pháp thuộc chủ đề A3 – AI Agent thấu hiểu đa định dạng tài liệu, với tên gọi FORGE: Factory Operation Retrieval & Generation Engine.

Để tóm tắt ngắn gọn nhất về FORGE: Đây là hệ thống RAG đa phương thức đầu tiên được thiết kế chuyên biệt cho tài liệu nhà máy với 3 đột phá lớn: Visual Grounding (khoanh vùng tọa độ hình ảnh), Aggregation (tổng hợp và đếm dữ liệu), và hỗ trợ Đa ngôn ngữ Việt - Nhật - Anh. Hướng tới tầm nhìn nhà máy tự động hóa local-first vào năm 2030 của DENSO, FORGE giúp giảm thời gian tra cứu tài liệu từ 30 đến 60 phút xuống chỉ còn dưới 2 giây, đồng thời đảm bảo an toàn dữ liệu tuyệt đối nhờ kiến trúc self-hosted hoàn toàn nội bộ.

### BẮT ĐẦU — SLIDE 3 — NGƯỜI TRÌNH BÀY: Phan Tuấn Minh
Để hiện thực hóa giải pháp này là sự kết hợp của 5 thành viên đến từ các chuyên ngành Kỹ thuật Phần mềm, Khoa học Dữ liệu và AI tại BUV:
Em là Tuấn Minh – Team Leader, phụ trách định hướng chung với kinh nghiệm R&D về AI Data Fusion trong kỹ thuật an toàn.
Bạn Khánh Linh phụ trách UI/UX và Business Analyst.
Bạn Tuấn Anh đảm nhiệm vai trò Data Curator, xử lý và chuẩn hóa dữ liệu.
Bạn Hoàng Cường là Agile Developer của nhóm.
Và bạn Minh Tiến là Technical Specialist với kinh nghiệm thực tập phát triển phần mềm thực tế.

Dù đây là lần đầu tiên cả đội cùng bắt tay xây dựng một hệ thống RAG hoàn chỉnh, nhưng nền tảng học thuật vững chắc cùng kinh nghiệm thực chiến từ các dự án cá nhân và kỳ thực tập chính là bệ phóng để chúng em tự tin giải quyết bài toán của DENSO.

### BẮT ĐẦU — SLIDE 4 — NGƯỜI TRÌNH BÀY: Phan Khánh Linh
Khi khảo sát quy trình vận hành tại nhà máy, chúng em nhận thấy một thực trạng lớn: Kiến thức vận hành đang nằm rải rác và phân mảnh trong vô số định dạng tài liệu khác nhau. Một quy trình chuẩn hay thông số kỹ thuật có thể nằm trong file Word, bảng tính Excel, tài liệu PDF, hoặc thậm chí là các bản vẽ, ảnh chụp và bản scan. Đặc biệt, các bảng biểu và sơ đồ kỹ thuật thường nằm lồng ghép ngay bên trong các tài liệu này.

Điều này dẫn đến 3 nỗi đau (Pain Points) trực tiếp cho kỹ sư nhà máy:
Thứ nhất là tra cứu cực kỳ chậm: Việc tập hợp đủ thông tin cần thiết giữa các phòng ban có thể mất từ 30 đến 60 phút cho một lần tìm kiếm thủ công.
Thứ hai là dễ bỏ sót dữ liệu quan trọng: Các công cụ tìm kiếm văn bản thông thường không thể đọc hiểu sâu các bảng biểu phức tạp hay hình ảnh nằm trong file scan.
Thứ ba là trả lời sai ngữ cảnh: Trong môi trường đặc thù của DENSO, tài liệu tồn tại ở cả 3 ngôn ngữ Việt, Anh và Nhật. Sự bất đồng ngôn ngữ khiến việc đối chiếu chéo trở nên vô cùng khó khăn.

### BẮT ĐẦU — SLIDE 5 — NGƯỜI TRÌNH BÀY: Phan Khánh Linh
Để giải quyết triệt để 3 vấn đề trên, chúng em đề xuất FORGE – một RAG Engine đóng vai trò là bộ não trung tâm: tiếp nhận mọi định dạng từ DOC, XLSX, PDF, ảnh chụp cho đến bản vẽ scan, sau đó xử lý và chuẩn hóa để kỹ sư có thể hỏi đáp tức thì qua một AI Chatbot có trích dẫn nguồn rõ ràng.

Để kiểm chứng năng lực của hệ thống một cách khoa học, chúng em xây dựng bộ dữ liệu đầu vào dựa trên 3 nguyên tắc: Đủ định dạng nhà máy – Tách bạch mục đích kiểm thử – Và 100% hợp pháp, mã nguồn mở. Cụ thể gồm 3 nhóm dữ liệu:
Thứ nhất là AI-generated pack: Bộ tài liệu nhà máy tổng hợp gồm PDF, bản scan, bảng tính để kiểm thử toàn bộ luồng xử lý pipeline.
Thứ hai là Curated Data: gồm 30 ảnh tài liệu nghiệp vụ tiếng Nhật từ [JA-Business-Doc-RQ-Bench trên Hugging Face](https://huggingface.co/datasets/stockmark/JA-Business-Doc-RQ-Bench) để kiểm thử khả năng hỏi đáp thị giác bằng tiếng Nhật, và 30 dữ liệu ốc vít đã được gán nhãn từ [Screw Dataset trên Hugging Face](https://huggingface.co/datasets/shrish23/screw-dataset) để kiểm thử nhận diện và phân đoạn lỗi sản phẩm.
Thứ ba là Golden dataset: Một tệp CSV gồm 25 câu hỏi và câu trả lời tham chiếu đa ngôn ngữ (15 câu tiếng Việt, 5 tiếng Nhật và 5 tiếng Anh) dùng làm thước đo chuẩn xác cho đầu ra của hệ thống.

### BẮT ĐẦU — SLIDE 6 — NGƯỜI TRÌNH BÀY: Trần Hoàng Cường
Tiếp nối phần dữ liệu, em xin phép trình bày sâu hơn về kiến trúc hệ thống của FORGE ở Slide 6 và hiệu quả thực tế mà kiến trúc này mang lại ở Slide 7.

Đi sâu vào kiến trúc kỹ thuật, FORGE được thiết kế thành 2 luồng xử lý tách biệt nhưng liên kết chặt chẽ thông qua giao diện Next.js và cổng FastAPI.

Luồng thứ nhất là Ingestion Pipeline, xử lý trên từng tài liệu tải lên:
Đầu tiên, tài liệu đầu vào được đưa qua Docling kết hợp OCR, TableFormer và mô hình ngôn ngữ thị giác Florence-2. Bước này giúp bóc tách chính xác bố cục văn bản, cấu trúc bảng biểu và tạo mô tả kèm tọa độ Visual Grounding cho hình ảnh.
Tiếp theo, HybridChunker sẽ chia nhỏ dữ liệu thành các khối có cấu trúc, giữ nguyên ngữ cảnh và siêu dữ liệu nguồn gốc.
Cuối cùng, mô hình BGE-M3 chuyển đổi dữ liệu thành cả Dense và Sparse vectors. File gốc sẽ được lưu tại Local FileSystem, Metadata lưu vào SQLite, và Vector được lưu trữ trong cơ sở dữ liệu Qdrant.

Luồng thứ hai là Query Pipeline, xử lý khi kỹ sư đặt câu hỏi:
Câu hỏi sẽ đi qua cơ chế Hybrid Retrieval trên Qdrant để lấy ra Top-K ứng viên tiềm năng nhất, sau đó được sắp xếp lại độ ưu tiên bằng Cross-Encoder Reranking.
Phần thông tin tinh lọc này được đưa vào mô hình Gemini, và dự kiến sẽ tích hợp trực tiếp DensoGPT nội bộ khi triển khai thực tế để sinh câu trả lời.
Điểm cốt lõi về mặt an toàn của FORGE nằm ở chốt chặn kiểm tra bằng chứng. Nếu đủ căn cứ, hệ thống mới đưa ra câu trả lời kèm trích dẫn nguồn. Ngược lại, nếu dữ liệu không đủ, hệ thống sẽ chủ động từ chối trả lời để tuyệt đối chống hiện tượng ảo giác trong môi trường sản xuất.

### BẮT ĐẦU — SLIDE 7 — NGƯỜI TRÌNH BÀY: Trần Hoàng Cường
Chuyển sang Slide 7, vậy kiến trúc này mang lại những con số định lượng cụ thể ra sao?

Về tốc độ tập hợp và xử lý dữ liệu: So với mức 30 đến 60 phút làm thủ công, FORGE rút ngắn thời gian xử lý xuống chỉ còn 10 đến 15 giây trên GPU, hoặc 60 đến 90 giây trên CPU. Đặc biệt, đối với thời gian tra cứu của mỗi câu hỏi, mục tiêu độ trễ P95 của chúng em là dưới 2 giây.

Trên bộ đo lường 100 truy vấn, chúng em cam kết các chỉ số mục tiêu rất khắt khe:
Thứ nhất, Context Recall và Faithfulness đều đạt từ 90% trở lên, đảm bảo truy xuất đủ tài liệu liên quan và câu trả lời hoàn toàn có căn cứ.
Thứ hai, F1 Answerability đạt tối thiểu 90% và chỉ số MRR tăng thêm ít nhất 0.1 sau bước Reranking.

Khi đặt lên bàn cân so sánh trực tiếp giữa phương pháp Thủ công, Azure Cloud RAG và FORGE:
Trong khi giải pháp đám mây như Azure tốn khoảng 500 đô mỗi tháng và gặp rào cản lớn là dữ liệu phải đưa lên Cloud bên thứ ba, thì FORGE vận hành Self-hosted 100%, đảm bảo tuyệt đối quyền riêng tư dữ liệu cho nhà máy với chi phí chỉ khoảng 2 đô mỗi tháng trên VPS, hoặc hoàn toàn miễn phí 0 đô khi dùng DensoGPT nội bộ.
Hơn thế nữa, FORGE giải quyết triệt để những điểm mà các giải pháp truyền thống và Cloud RAG còn hạn chế: đó là hỗ trợ sâu song ngữ Việt - Nhật qua BGE-M3, định vị hình ảnh Visual Grounding qua Florence-2, và khả năng đếm, tổng hợp dữ liệu Aggregation thông qua Query Router.

### BẮT ĐẦU — SLIDE 8 — NGƯỜI TRÌNH BÀY: Bùi Minh Tiến
Để làm rõ hơn vì sao FORGE có thể tối ưu chi phí vận hành xuống mức thấp như vậy, ở Slide 8 chúng em liệt kê chi tiết toàn bộ Tech Stack theo từng lớp kiến trúc.

Như Ban giám khảo có thể thấy, toàn bộ các lớp từ Giao diện Next.js, cổng FastAPI, công cụ xử lý tài liệu Docling, mô hình thị giác Florence-2, mô hình Embedding BGE-M3, cơ sở dữ liệu vector Qdrant cho đến bộ Reranker đều sử dụng các công nghệ mã nguồn mở với giấy phép thương mại hợp lệ như MIT hoặc Apache-2.0. Nhờ đó, chi phí bản quyền phần mềm ở tất cả các tầng này là 0 đô la. Dữ liệu và siêu dữ liệu được lưu trữ ngay trên hạ tầng ổ đĩa sẵn có cùng SQLite cho bản demo và PostgreSQL cho giai đoạn pilot.

Chi phí biến đổi duy nhất nằm ở lớp Sinh câu trả lời nếu sử dụng Gemini 3.5 Flash-Lite, nhưng cũng chỉ tốn khoảng 0.00275 đô la cho mỗi lượt hỏi, tức khoảng 28 cent cho 100 lượt truy vấn. Và đặc biệt, khi triển khai thực tế và kết nối vào endpoint DensoGPT nội bộ của nhà máy, chi phí API này sẽ hoàn toàn bằng 0.

Đầu ra cuối cùng mà FORGE trao tận tay kỹ sư nhà máy luôn đảm bảo 3 cam kết:
Một là câu trả lời có căn cứ xác thực dựa trên tài liệu truy xuất được.
Hai là luôn đính kèm nguồn trích dẫn để kiểm chứng ngay lập tức.
Và ba là minh bạch nêu rõ khi hệ thống chưa đủ dữ liệu, tuyệt đối không đoán mò.

### BẮT ĐẦU — SLIDE 9 — NGƯỜI TRÌNH BÀY: Bùi Minh Tiến
Không chỉ dừng lại ở chi phí phần mềm, chúng em đã tính toán một bài toán ROI (Hiệu quả đầu tư) hết sức thận trọng và minh bạch để chứng minh tính khả thi khi vận hành thực tế tại nhà máy.

Với giả định bảo thủ trong năm đầu tiên: Chỉ cần 20% kỹ sư áp dụng (tức 20 người trên 100 kỹ sư), mỗi người tra cứu 1 lần mỗi ngày trong 220 ngày làm việc. Việc rút ngắn thời gian từ 20 phút xuống dưới 2 giây giúp tiết kiệm khoảng 1,467 giờ công mỗi năm. Nhân với chi phí nhân sự ước tính 6 đô la một giờ, nhà máy tiết kiệm được 8,800 đô la mỗi năm.

Ngay cả khi chúng ta tính đầy đủ chi phí vận hành toàn diện là 8,000 đô la một năm (đã bao gồm thuê GPU, VPS, API, chi phí nhân sự rà soát và bảo trì hệ thống), thì ngay trong Năm thứ nhất, DENSO đã có lợi nhuận ròng (Net Savings) là 800 đô la, đạt ROI khoảng 10% và hoàn vốn (Break-even) chỉ sau 11 tháng.

Từ Năm thứ 2 trở đi, khi tỷ lệ kỹ sư sử dụng tăng lên mức 50 đến 70%, ROI ước tính sẽ bứt phá lên mức 200% đến 500%. Bên cạnh con số tài chính, 3 lợi ích định tính vô giá mà FORGE mang lại là: Giảm thiểu sai sót vận hành do tra cứu thủ công, giữ lại tri thức nhà máy ngay cả khi các chuyên gia kỳ cựu nghỉ hưu, và giúp kỹ sư mới tự onboarding nhanh chóng mà không cần chờ đợi nhân sự senior hướng dẫn.

### BẮT ĐẦU — SLIDE 10 — NGƯỜI TRÌNH BÀY: Nguyễn Tuấn Anh
Để biến bản thiết kế này thành sản phẩm chạy thực tế tại nhà máy, chúng em đã vạch ra lộ trình triển khai kéo dài 6 tuần (từ 20/10 đến 24/11/2026), làm việc sát sao cùng các anh chị Denso Mentor:

Giai đoạn 1 (từ 20 đến 23/10): Kickoff cùng Mentor và chốt phạm vi dự án cũng như dữ liệu tại cổng kiểm soát Gate 1 vào ngày 23/10.
Giai đoạn 2 (từ 23 đến 27/10): Chuẩn hóa dữ liệu, xây dựng luồng Ingestion và chuẩn bị dữ liệu cho Florence-2.
Giai đoạn 3A và 3B (từ 27/10 đến 07/11): Chạy song song việc phát triển lõi RAG (gồm API, Query Router, Qdrant, tích hợp giao diện) và tinh chỉnh Fine-tune mô hình Florence-2 bằng LoRA qua 2 lượt huấn luyện.
Giai đoạn 4 (từ 07 đến 14/11): Tối ưu hóa lõi hệ thống như đánh chỉ mục Payload, tinh chỉnh thuật toán HNSW và thiết lập hệ thống giám sát monitoring.
Giai đoạn 5A và 5B (từ 14 đến 21/11): Đo lường thực tế các chỉ số Latency, Faithfulness, Context Recall, độ chính xác IoU của Visual Grounding; đồng thời chạy thử nghiệm nâng cao Semantic Caching và Quantization để sẵn sàng mở rộng quy mô.
Giai đoạn 6 (từ 21 đến 24/11): Chạy Final Pilot cùng Denso Mentor để nghiệm thu và chốt kết quả thực tế.

### BẮT ĐẦU — SLIDE 11 — NGƯỜI TRÌNH BÀY: Phan Tuấn Minh
Tóm lại, tại sao FORGE lại là mảnh ghép phù hợp nhất cho DENSO ở thời điểm hiện tại?
Một là tính toàn diện: Giải quyết trọn vẹn bài toán tài liệu phân mảnh, đọc hiểu sâu từ bảng biểu phức tạp đến hình ảnh bản vẽ bằng cả tiếng Việt, tiếng Nhật và tiếng Anh.
Hai là hiệu suất vượt trội với chi phí tối ưu: Đưa thời gian tìm kiếm từ hàng chục phút về dưới 2 giây với độ chính xác trên 90%, hoàn vốn ngay trong năm đầu tiên.
Và ba là khả năng mở rộng bền vững: Với kiến trúc offline-first, bảo mật nội bộ hoàn toàn và khả năng tích hợp trực tiếp DensoGPT, FORGE không chỉ giải quyết bài toán cho một phòng ban mà có thể nhân rộng ngang sang bất kỳ nhà máy nào của DENSO, đặt nền móng vững chắc cho mục tiêu nhà máy tự động hóa năm 2030.

"FORGE biến tri thức đang phân tán trong nhà máy thành tri thức có thể tìm thấy, kiểm chứng và chia sẻ — để mỗi kỹ sư dành ít thời gian tìm kiếm hơn và nhiều thời gian hơn cho công việc tạo giá trị."

Ban giám khảo có thể trải nghiệm giao diện demo tại [forge-factory-demo.vercel.app](https://forge-factory-demo.vercel.app/) và xem mã nguồn dự án tại [GitHub của Team UNICORN](https://github.com/CuongMe/FORGE-Denso-Hackathon-Team-UNICORN-BUV-ongoing). Các đường link và mã QR cũng được hiển thị trên slide.

### BẮT ĐẦU — SLIDE 12 — NGƯỜI TRÌNH BÀY: Phan Tuấn Minh
Đội UNICORN đã sẵn sàng cho hành trình 6 tuần sắp tới. Cảm ơn Ban giám khảo đã lắng nghe, chúng em rất mong nhận được các câu hỏi và góp ý từ các anh chị!

## Bảng phân chia slide theo từng thành viên

### Phan Tuấn Minh (Team Leader)
- **Slide 1 & 2:** Mở đầu và giới thiệu FORGE cùng các giá trị cốt lõi.
- **Slide 3:** Giới thiệu đội ngũ UNICORN.
- **Slide 11 & 12:** Tổng kết và lời cảm ơn.

### Phan Khánh Linh (UI/UX & Business Analyst)
- **Slide 4 & 5:** Vấn đề thực tế tại nhà máy (Pain Points), giải pháp đề xuất và chiến lược dữ liệu đầu vào.

### Trần Hoàng Cường (Agile Developer)
- **Slide 6 & 7:** Kiến trúc FORGE, hiệu quả mang lại và các chỉ số mục tiêu.

### Bùi Minh Tiến (Technical Specialist)
- **Slide 8 & 9:** Tech stack, chi phí công nghệ, đầu ra của FORGE và bài toán ROI.

### Nguyễn Tuấn Anh (Data Curator)
- **Slide 10:** Kế hoạch triển khai 6 tuần cùng DENSO Mentor.
