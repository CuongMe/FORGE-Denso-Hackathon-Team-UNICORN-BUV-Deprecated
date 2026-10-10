type DemoQuery = {
  label: string;
  description: string;
  question: string;
  nativeLanguage?: "ja" | "vi";
  expectedAnswer?: string;
};

export const demoQueries: DemoQuery[] = [
  {
    label: "Structured lookup",
    description: "Find a controlled process value",
    question: "What is the target torque for the M6 bolts?",
  },
  {
    label: "Cross-language",
    description: "English query, Vietnamese evidence",
    question: "What pressure must be zero before zero energy is confirmed?",
  },
  {
    label: "Honest Demo",
    description: "Ask outside the indexed evidence",
    question: "Who won the football match yesterday?",
  },
  {
    label: "Out-of-range response",
    description: "Apply the torque exception procedure",
    question: "What should the operator do if an M6 bolt torque is out of range?",
  },
  {
    label: "Defect escalation",
    description: "Check the defect escalation deadlines",
    question: "When must a defect be escalated and an NCR created?",
  },
  {
    label: "Maintenance limits",
    description: "Find the pressure range and abnormality action",
    question: "What air-pressure range is acceptable for Servo Press SP-04?",
  },
  {
    label: "JA · 輸送",
    description: "日本語の質問 · 日本語の根拠",
    question: "以下の条件をすべて満たす輸送モードを特定せよ。 1. CO2排出強度が 30 g/t・km未満である。 2.輸送量が60億トンキロを超えている。",
    nativeLanguage: "ja",
    expectedAnswer: "船舶です。輸送量は67.5億トンキロで、CO2排出強度は15 g/t・kmです。",
  },
  {
    label: "JA · 設備",
    description: "日本語の質問 · 日本語の根拠",
    question: "ある配送ミッションで「積載重量 20kg」を運ぶ必要がある。図1において、この重量で「必要電力が 30kW 以下」に収まる唯一のモーター型式を特定し、ペアになる冷却方式が「飛行時間 60分」の時に記録している「熱管理効率（％）」を答えよ。（モーター型式とペアになる冷却方式：M1-C1, M2-C2, M3-C4, M4-C3, M5-C5）",
    nativeLanguage: "ja",
    expectedAnswer: "モーター型式はM3で、対応する冷却方式C4の熱管理効率は92%です。",
  },
  {
    label: "JA · 安全性",
    description: "日本語の質問 · 日本語の根拠",
    question: "以下の条件をすべて満たす、機体モデルの名称を答えよ。 1. 安定性指数が、全モデルの平均を超えている。 2. 消費電力が、「H4高度、T1時間帯」の乱気流強度よりも「低い」。",
    nativeLanguage: "ja",
    expectedAnswer: "両方の条件を満たす機体モデルはM1です。",
  },
  {
    label: "JA · コスト",
    description: "日本語の質問 · 日本語の根拠",
    question: "構成比率が最大であるミッションを特定し、そのミッションに従事している艦艇が「1日あたり」に消費する燃料コストの合計額は何百万円ですか？なお、燃料コストは1隻あたりの数値です。",
    nativeLanguage: "ja",
    expectedAnswer: "最大のミッションは採掘です。燃料コストの合計は1日あたり8,960百万円です。",
  },
  {
    label: "VI · Vận tải",
    description: "Câu hỏi tiếng Việt · bằng chứng tiếng Nhật",
    question: "Theo tài liệu JA-BIZ-0001, phương thức vận tải nào vừa có cường độ phát thải CO2 dưới 30 g/t-km, vừa có khối lượng vận chuyển trên 6 tỷ tấn-km?",
    nativeLanguage: "vi",
    expectedAnswer: "Vận tải đường biển đáp ứng điều kiện: cường độ CO2 là 15 g/t-km và khối lượng vận chuyển là 6,75 tỷ tấn-km.",
  },
  {
    label: "VI · Thiết bị",
    description: "Câu hỏi tiếng Việt · bằng chứng tiếng Nhật",
    question: "Theo tài liệu JA-BIZ-0004, với tải trọng 20 kg, kiểu động cơ nào cần không quá 30 kW và hiệu suất quản lý nhiệt của phương thức làm mát tương ứng ở thời gian bay 60 phút là bao nhiêu?",
    nativeLanguage: "vi",
    expectedAnswer: "Động cơ M3 là kiểu duy nhất đáp ứng điều kiện; phương thức làm mát C4 đạt hiệu suất nhiệt 92% ở thời gian bay 60 phút.",
  },
  {
    label: "VI · An toàn",
    description: "Câu hỏi tiếng Việt · bằng chứng tiếng Nhật",
    question: "Theo tài liệu JA-BIZ-0006, mẫu máy bay nào có chỉ số ổn định cao hơn mức trung bình và công suất thấp hơn cường độ nhiễu động tại độ cao H4, khung giờ T1?",
    nativeLanguage: "vi",
    expectedAnswer: "Mẫu máy bay M1 đáp ứng đồng thời cả hai điều kiện.",
  },
  {
    label: "VI · Chi phí",
    description: "Câu hỏi tiếng Việt · bằng chứng tiếng Nhật",
    question: "Theo tài liệu JA-BIZ-0009, nhiệm vụ chiếm tỷ trọng 35% nào có tổng chi phí nhiên liệu mỗi ngày cao nhất nếu có 800 tàu và mỗi tàu tốn 32 triệu yên?",
    nativeLanguage: "vi",
    expectedAnswer: "Nhiệm vụ khai thác mỏ chiếm tỷ trọng lớn nhất (35%); tổng chi phí nhiên liệu là 8.960 triệu yên mỗi ngày.",
  },
];

