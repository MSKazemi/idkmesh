# IDKMesh

[![PR Gate](https://github.com/MSKazemi/idkmesh/actions/workflows/pr-gate.yml/badge.svg?branch=main)](https://github.com/MSKazemi/idkmesh/actions/workflows/pr-gate.yml)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](pyproject.toml)
[![good first issues](https://img.shields.io/github/issues/MSKazemi/idkmesh/good%20first%20issue?label=good%20first%20issues&color=7057ff)](https://github.com/MSKazemi/idkmesh/issues?q=is%3Aissue+state%3Aopen+label%3A%22good+first+issue%22)

**Ngôn ngữ:** [English](README.md) • Tiếng Việt

> **Ghi chú về bản dịch:** Bản dịch tiếng Việt này được đối chiếu từ bản gốc tiếng Anh tại commit `785bed8e97c2733391ea4f6d9c7efa85759e6712`. Trong trường hợp tài liệu gốc có sự cập nhật hoặc sai khác, vui lòng tham khảo file `README.md` tiếng Anh làm chuẩn.

> **Tôi không biết. Bạn không biết. Cùng nhau, mạng lưới (mesh) có thể khám phá, xây dựng, xác minh và học hỏi.**

IDKMesh là một dự án nghiên cứu và kỹ thuật mã nguồn mở nhằm khám phá cách con người, các tác tử AI (AI agents), công cụ phần mềm và các hệ thống tính toán không đồng nhất có thể phối hợp với nhau hướng tới các mục tiêu chưa chắc chắn, từ đó biến các đề xuất thành **kết quả hữu ích đã được xác minh (verified useful work)**.

Dự án có định hướng đầy tham vọng, nhưng repository này không tuyên bố đã hoàn thiện một hệ thống quy mô hành tinh. Hiện tại, đây là một **phòng thí nghiệm nghiên cứu vận hành trên nền tảng GitHub với nền tảng bằng chứng/phối hợp có thể thực thi** cùng một mục tiêu sản phẩm tham chiếu: Git-native Verified Swarm Runner.

**Một câu hỏi cụ thể mà repository này đã có thể trả lời:** *hội đồng đánh giá của bạn thực sự có giá trị tương đương bao nhiêu phiếu bầu độc lập?* Con số thực tế thường ít hơn nhiều so với số lượng thành viên đánh giá trên danh nghĩa. Trong thử nghiệm [E017](experiments/E017-item-difficulty-and-quorum.md), một hội đồng gồm 25 bộ xác minh (verifier) — trong đó mỗi verifier là một chương trình, và mỗi lỗi là một khiếm khuyết bị bỏ sót được quan sát thực tế — đã cho thấy quy mô hiệu dụng chỉ đạt **1.00 trên 25**: khi bỏ phiếu theo đa số, toàn bộ hội đồng không có giá trị hơn một thành viên đơn lẻ, trong khi công thức hiệu chỉnh phổ biến `N/(1+(N-1)rho)` dự đoán là 1.66. Lệnh [`idkmesh gate-audit`](#thử-nghiệm-trong-năm-phút-kiểm-toán-một-cổng-đánh-giá) thực hiện phép đo đó trên các phán quyết bạn đã thu thập và báo cáo các mẫu thử lỗi đã biết bị hội đồng bỏ lọt.

## Thử nghiệm bản demo hợp đồng

Với Git và Python 3.11 hoặc 3.13, hãy sử dụng môi trường ảo. Ví dụ trên Linux/macOS:

```bash
git clone https://github.com/MSKazemi/idkmesh && cd idkmesh
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-phase0.txt
python scripts/demo.py
```

Đối với Windows, vui lòng xem hướng dẫn thiết lập môi trường trong [CONTRIBUTING.md](CONTRIBUTING.md).
Không yêu cầu tài khoản mô hình hay API key. Thời gian cài đặt phụ thuộc vào môi trường của bạn.

Bản demo này xác thực các **dữ liệu mẫu tổng hợp (synthetic fixtures)** đã được commit cùng với các validator và schema thực tế trong [`schemas/`](schemas/) và dữ liệu đầu vào trong [`examples/`](examples/).
Bản demo thực hiện ba lượt kiểm tra hợp lệ và bốn lượt kiểm tra từ chối có chủ đích:

| Dữ liệu mẫu không hợp lệ | Lý do bị từ chối |
| --- | --- |
| Một tác vụ không có hợp đồng bảo mật | một hợp đồng có thể điều phối phải khai báo ranh giới bảo mật của nó |
| Kết quả của worker tự chấp nhận chính nó | việc worker hoàn thành công việc không đồng nghĩa với việc được chấp nhận |
| Một verifier sử dụng danh tính của worker | chính worker không thể tự thỏa mãn hợp đồng verifier độc lập |
| Một kết quả xác minh có nguồn gốc (provenance) không khớp | bằng chứng phải gắn liền chặt chẽ với các thành phần (artifact) được cung cấp |

**Không có worker trực tiếp hay verifier bên ngoài nào được thực thi.** Một dữ liệu mẫu vượt qua kiểm tra không phải là bằng chứng cho sự độc lập trong thế giới thực, công việc chính xác, hay quyền được merge. Các lỗi quy trình hoặc lỗi lập trình ngoài ý muốn sẽ làm bản demo thất bại, thay vì được tính là bằng chứng từ chối thành công.

Các câu hỏi và thảo luận về lý do triển khai được trao đổi tại mục [Discussions](https://github.com/MSKazemi/idkmesh/discussions); hệ thống issue tracker chỉ dành cho các khiếm khuyết (defect) và các tác vụ có phạm vi giới hạn rõ ràng. Đối với các tác vụ cụ thể hoặc chia sẻ trách nhiệm kỹ thuật, vui lòng xem [thư mời cộng tác](https://github.com/MSKazemi/idkmesh/issues/407).

## Câu hỏi trọng tâm

> **Liệu một cộng đồng mở rộng lớn gồm con người và các tác tử AI có thể khám phá mục tiêu, phân rã công việc, thực thi các tác vụ có giới hạn, xác minh kết quả độc lập và duy trì các hệ thống phức tạp tốt hơn các lập trình viên hoặc tác tử hoạt động biệt lập hay không?**

IDKMesh coi đây là một câu hỏi thực nghiệm. Thêm nhiều tác tử, nhiều hoạt động hơn, nhiều commit hơn hay nhiều phiếu bầu hơn không tự động đồng nghĩa với tốt hơn.

## Trạng thái hiện tại

**Nền tảng nghiên cứu có thể thực thi; trình chạy tham chiếu (reference runner) vẫn chưa hoàn thiện.**

Những gì đã có sẵn trên nhánh `main`:

- Các hợp đồng WorkUnit có phiên bản, với `work-unit-v0.2.schema.json` là hợp đồng tác vụ ngữ nghĩa hiện tại;
- Các hợp đồng ResultManifest, EvaluatorPlan và VerificationResult tách biệt rõ ràng giữa tuyên bố của worker, bằng chứng của verifier và thẩm quyền tích hợp;
- Cơ chế xác thực tính toàn vẹn và nguồn gốc liên đối tượng (cross-object provenance);
- Hợp đồng benchmark phân rã WorkUnit năm nhánh (five-arm) cùng ranh giới bằng chứng nghiêm ngặt giữa dữ liệu tổng hợp và dữ liệu quan sát thực nghiệm;
- Mã adapter cho worker trung lập về giao thức cùng với các liên kết A2A/MCP và công cụ hỗ trợ chuẩn tương thích (conformance helpers) trong thư mục [`interop/`](interop/);
- Mã nguồn mô phỏng và thử nghiệm trong [`sim/`](sim/) và [`experiments/`](experiments/);
- Các thử nghiệm định tuyến và chấp nhận tài nguyên tính toán với chi phí dự án bằng không;
- Cơ chế mô hình hóa repository IDKGraph, khả năng quan sát (observability), tính toàn vẹn liên kết và hệ thống cảnh báo/đánh giá;
- Các thử nghiệm tăng trưởng cộng đồng ACE nguyên bản trên GitHub và công cụ kiểm soát tiến hóa repository;
- Giao diện sản phẩm có thể cài đặt đầu tiên: `pip install .` cung cấp CLI `idkmesh`, trong đó lệnh `gate-audit` đóng gói các kết quả đo lường hội đồng verifier (E015/E016/E017) thành một công cụ chẩn đoán cổng đánh giá;
- Nhánh `main` được bảo vệ với cổng PR ổn định yêu cầu chạy trên Python 3.11 và 3.13.

Những gì **chưa** phải là khả năng đã hoàn thiện:

- Không có tuyên bố nào khẳng định IDKMesh có thể phối hợp an toàn hàng nghìn hay hàng triệu máy tính thực tế;
- Trình chạy tham chiếu Verified Swarm Runner vẫn chưa phải là một sản phẩm hoàn chỉnh để cài đặt-và-chạy với nhiều adapter worker sẵn sàng cho môi trường production;
- Việc tích hợp node thực chuẩn mực vẫn phải tuân theo các cổng bằng chứng/đánh giá độc lập, thay vì được suy đoán từ các nguyên mẫu lịch sử;
- Hỗ trợ A2A/MCP chỉ là lớp tương tác (interoperability layer), không phải tuyên bố rằng mọi framework tác tử bên ngoài đều đã được tích hợp trong production;
- Hoạt động tự trị trên repository/cộng đồng vẫn phải chịu sự kiểm soát chặt chẽ của chính sách và quyền hạn;
- Cơ sở hạ tầng benchmark không phải là bằng chứng khoa học cho đến khi có các lượt chạy quan sát được kiểm soát.

Sự phân biệt này rất quan trọng: **cơ sở hạ tầng được triển khai là bằng chứng về khả năng chạy thử nghiệm, chứ không phải bằng chứng cho thấy các giả thuyết nghiên cứu là đúng.**

## Thử nghiệm trong năm phút: kiểm toán một cổng đánh giá

Công cụ cài đặt đầu tiên được trích xuất từ nghiên cứu này là `idkmesh gate-audit`. Nó đo lường giá trị thực tế của một hội đồng người đánh giá/verifier: số phiếu độc lập hiệu dụng (chứ không phải số lượng đầu người danh nghĩa), cấu trúc tương quan lỗi, và tỷ lệ lọt lưới của các mẫu thử lỗi đã biết.

```bash
git clone https://github.com/MSKazemi/idkmesh
cd idkmesh
pip install .
idkmesh gate-audit examples/gate-audit/panel-votes.example.json --pretty
```

Ví dụ đi kèm báo cáo rằng một hội đồng gồm 5 verifier chỉ có giá trị tương đương khoảng **1.69 phiếu bầu độc lập hiệu dụng**, và phương pháp phỏng đoán phổ biến `N/(1+(N-1)ρ)` đã ước tính quá cao — hiện tượng này đã được đo lường trên một hội đồng 25 verifier thực tế trong [E017](experiments/E017-item-difficulty-and-quorum.md) và bị bác bỏ như một quy tắc xác định quy mô trong [E015](experiments/E015-verification-phase-diagram.md). Hợp đồng được quy định tại [`docs/specifications/GATE_AUDIT_V0_1.md`](docs/specifications/GATE_AUDIT_V0_1.md). Việc kiểm toán chỉ mang tính chẩn đoán: nó sử dụng các phán quyết bạn đã thu thập và không cấp thẩm quyền chấp nhận hay merge. Trong CI, quá trình kiểm toán tương tự chạy như một GitHub Action:

```yaml
- uses: MSKazemi/idkmesh/actions/gate-audit@main
  with:
    votes-file: path/to/panel-votes.json
```

## Bắt đầu tại đây

Bạn không cần phải hiểu toàn bộ repository trước khi đóng góp.

1. Đọc file README này.
2. Đọc [`CONTRIBUTING.md`](CONTRIBUTING.md).
3. Chọn một lộ trình đóng góp trong [`COMMUNITY.md`](COMMUNITY.md).
4. Duyệt qua các danh sách issue đang mở có nhãn [`good first issue`](https://github.com/MSKazemi/idkmesh/issues?q=is%3Aissue+state%3Aopen+label%3A%22good+first+issue%22) và [`help wanted`](https://github.com/MSKazemi/idkmesh/issues?q=is%3Aissue+state%3Aopen+label%3A%22help+wanted%22).
5. Trước khi bắt đầu, hãy kiểm tra người được giao (assignees), các bình luận gần đây, các pull request liên quan, sau đó nêu rõ phạm vi thay đổi có giới hạn mà bạn dự định thực hiện.

Hai ví dụ trực tiếp tại thời điểm kiểm toán này:

- [#167 — độc lập đánh giá nhóm cô lập IDKGraph đợt 1](https://github.com/MSKazemi/idkmesh/issues/167), một tác vụ đánh giá/bằng chứng thân thiện với người mới;
- [#151 — độc lập kiểm toán mặt phẳng kiểm soát tiến hóa toán học](https://github.com/MSKazemi/idkmesh/issues/151), một tác vụ đánh giá hệ thống kiểm soát/bảo mật yêu cầu kỹ năng cao hơn.

[ACE Bootstrap Cohort Observatory](https://github.com/MSKazemi/idkmesh/issues/109) là nguồn bằng chứng trực tiếp cho đợt tăng trưởng ban đầu. Nó phân biệt rõ ràng giữa hoạt động bề nổi và sự tham gia thực tế đã được xác minh từ bên ngoài.

Nếu có điều gì khó hiểu, lỗi thời, mâu thuẫn hoặc khó khám phá, việc báo cáo hoặc sửa đổi điều đó đều là đóng góp hữu ích cho dự án.

## IDKMesh trong 60 giây

- **IDK** có nghĩa là *I Don't Know* (Tôi không biết): sự không chắc chắn, bất đồng, các giả định và các giả thuyết cạnh tranh là những trạng thái hạng nhất (first-class states).
- **Mesh** có nghĩa là một mạng lưới gồm con người, tác tử, công cụ, bằng chứng, tác vụ và năng lực tính toán, thay vì một tác tử nguyên khối duy nhất.
- Các worker chỉ nên nhận các **Work Unit** có phạm vi giới hạn, không phải toàn quyền kiểm soát dự án.
- Việc worker hoàn thành không đồng nghĩa với chấp nhận; khuyến nghị của verifier không phải là thẩm quyền merge.
- Việc xác minh, truy xuất nguồn gốc, khả năng tái lập và bảo mật phải mở rộng tương xứng với khối lượng tạo ra.
- Sự đa dạng chỉ có ý nghĩa khi nó đóng góp thêm bằng chứng hữu ích và đủ độc lập.
- Git/GitHub là nền tảng cộng tác và lưu trữ lịch sử chuẩn mực hiện tại.
- A2A và MCP là các bề mặt tích hợp; IDKMesh không nên phát minh lại các giao thức truyền tải thông thường khi không cần thiết.
- Repository công khai cũng chính là bộ nhớ của dự án: các quyết định lâu dài, phát hiện, bằng chứng và lịch sử cộng tác quan trọng phải luôn có thể kiểm tra được.

## Sản phẩm tham chiếu

Ứng dụng tham chiếu đầu tiên là **Git-native Verified Swarm Runner**.

Vòng đời mục tiêu là:

```text
tác vụ repository có giới hạn
        |
        v
   WorkUnit v0.2
        |
        v
 các worker adapter có thể thay thế
        |
        v
 artifact ứng viên + ResultManifest
        |
        v
 EvaluatorPlan do verifier sở hữu
        |
        v
 VerificationResult độc lập
        |
        v
 bằng chứng/báo cáo không tự lựa chọn
        |
        v
 quyết định tích hợp rõ ràng từ con người/quản trị
```

Quy tắc phân quyền then chốt là:

```text
thành công của worker != chấp nhận
khuyến nghị của verifier != thẩm quyền merge
thành công của CI != đánh giá độc lập từ con người
```

Mã nguồn hiện tại đã triển khai các phần quan trọng của quy trình tin cậy này, nhưng sản phẩm hoàn chỉnh từ đầu đến cuối cho người mới vẫn đang được tích hợp và kiểm nghiệm thực tế. Xem [`EVOLUTION.md`](EVOLUTION.md), [`ROADMAP.md`](ROADMAP.md), và các issue đang mở của dự án để biết các cổng kiểm soát hiện tại.

## Chạy các kiểm tra repository

Đối với mã nguồn nghiên cứu/điều khiển bằng Python của repository:

```bash
python -m pip install --disable-pip-version-check pytest
python -m pip install --disable-pip-version-check -r requirements-phase0.txt
PYTHONPATH=. python -m pytest -q
```

Xác thực trực tiếp các hợp đồng Giai đoạn 0 cốt lõi bằng:

```bash
python experiments/harness.py validate
```

Các pull request tới nhánh `main` được bảo vệ sẽ chạy cổng PR ổn định trên Python 3.11 và 3.13 cùng kiểm tra tính toàn vẹn liên kết Markdown xác định. Các hệ thống con riêng biệt cũng có các luồng kiểm tra hẹp hơn.

## Kiến trúc cốt lõi

IDKMesh được hiểu rõ nhất như một hệ thống phân tầng:

```text
hiến pháp con người / quản trị
           |
           v
 mục tiêu + câu hỏi + bằng chứng
           |
           v
       Work Units
           |
           v
 khớp nối năng lực / tài nguyên
           |
           v
 con người / tác tử / công cụ / tính toán độc lập
           |
           v
 artifact ứng viên + nguồn gốc
           |
           v
 xác minh / phản biện độc lập
           |
           v
 quyết định tích hợp rõ ràng
           |
           v
 trạng thái chuẩn mực + bằng chứng kết quả
           |
           +------> mục tiêu tiếp theo / học tập chính sách
```

Từ vựng vòng đời chuẩn mực — event, action, candidate, iteration, generation, learning, và improvement — được định nghĩa trong [`ITERATION_MODEL.md`](ITERATION_MODEL.md).

Đối với các ranh giới cấp độ triển khai, xem [`ARCHITECTURE.md`](ARCHITECTURE.md) và chỉ mục tài liệu tại [`docs/architecture/`](docs/architecture/README.md).

## Những gì IDKMesh xây dựng so với tái sử dụng

IDKMesh tập trung ngân sách độ phức tạp vào các phần thể hiện luận điểm nghiên cứu của mình:

- mục tiêu, sự không chắc chắn, và bằng chứng;
- Work Unit có giới hạn và quyền hạn;
- phân rã và cấu trúc phụ thuộc;
- khớp nối năng lực và tài nguyên;
- xác minh độc lập và tổng hợp bằng chứng;
- nguồn gốc và khả năng tái lập;
- cơ chế thử nghiệm và benchmark;
- vòng phản hồi cộng đồng và quản trị;
- tự cải tiến được đo lường dưới các ràng buộc quyền hạn bên ngoài.

Cơ sở hạ tầng thông dụng thường nên được tích hợp thay vì phát minh lại. Các ví dụ hiện tại bao gồm Git/GitHub, các mô hình cách ly kiểu OCI, A2A, MCP, và các phương pháp chuỗi cung ứng/nguồn gốc đã được thiết lập.

## Kỷ luật nghiên cứu

Repository này phân biệt ít nhất bốn trạng thái:

1. **cơ chế đã triển khai (implemented mechanism)** — mã nguồn/schema/workflow đã tồn tại;
2. **xác thực tổng hợp (synthetic validation)** — các fixture/mô phỏng xác định kiểm tra cơ chế hoạt động;
3. **bằng chứng quan sát (observed evidence)** — các lượt chạy có kiểm soát đo lường hành vi thực tế;
4. **kết luận được chấp nhận (accepted conclusion)** — bằng chứng đủ mạnh cho quyết định trong phạm vi xem xét.

Không đánh đồng các trạng thái này với nhau. Một bộ mô phỏng có thể xác thực việc triển khai của một thuật toán mà không chứng minh được rằng thuật toán đó cải thiện sự cộng tác trong thực tế.

Một nhóm nghiên cứu tiêu biểu so sánh, dưới cùng mức ngân sách:

```text
một worker mạnh
so với một worker nhỏ
so với các worker nhân bản
so với các worker không đồng nhất
so với các vai trò chuyên biệt
so với các nhóm đồ thị có hướng (DAG) tác vụ/bằng chứng
```

Các kết quả quan trọng bao gồm tính chính xác, thành công trong các bài kiểm tra ẩn, kiểm soát hồi quy (regressions), tương quan lỗi, thời gian của người đánh giá, sử dụng tài nguyên/tính toán, độ trễ, xung đột tích hợp, chất lượng nguồn gốc, và kết quả hữu ích đã được xác minh trên mỗi đơn vị chú ý/chi phí khan hiếm.

Xem [`RESEARCH_QUESTIONS.md`](RESEARCH_QUESTIONS.md), [`docs/research/`](docs/research/README.md), và [`experiments/`](experiments/).

## Các nguyên tắc của dự án

**Cộng đồng là trên hết.** Trải nghiệm của người đóng góp, năng lực đánh giá và khả năng mở rộng của đội ngũ lãnh đạo là những ràng buộc kỹ thuật.

**Đề xuất không phải là bằng chứng.** Sự tự tin của con người hay AI không thay thế được bằng chứng thực nghiệm.

**Mức độ phổ biến không phải là tính đúng đắn.** Số phiếu, số star, danh tiếng hay sự đồng thuận giữa các mô hình không thể vượt qua các bài kiểm tra thất bại.

**Nhiều tác tử hơn không tự động tốt hơn.** Sự đa dạng, tính độc lập, chất lượng phân rã và năng lực xác minh quan trọng hơn số lượng thô.

**Sự không chắc chắn là dữ liệu.** Các mục tiêu cạnh tranh và các giả thuyết chưa được giải quyết phải được thể hiện rõ ràng khi bằng chứng chưa đủ.

**Tốc độ tạo ra không được vượt quá năng lực xác minh.** Khối lượng đầu ra lớn sẽ gây hại nếu dự án không thể đánh giá, tái lập và duy trì nó.

**Tích hợp trước khi phát minh lại.** Tái sử dụng các tiêu chuẩn mở cho các khả năng thông dụng và giữ ngữ nghĩa đặc thù của IDKMesh ở lớp phối hợp/bằng chứng.

**Quy mô phải được chứng minh.** Các kết quả mô phỏng hoặc quy mô nhỏ không được quảng bá như những đảm bảo ở quy mô Internet.

**Nguồn gốc mật mã đi trước blockchain.** Chỉ bổ sung cơ sở hạ tầng tin cậy nặng hơn khi mô hình đe dọa thực tế đòi hỏi điều đó.

**Thẩm quyền chuẩn mực luôn nằm ngoài các bộ tạo và bộ xác minh.** Quyết định tích hợp được bảo vệ là một ranh giới quyết định riêng biệt.

## Cẩm nang repository

### Dành cho người đóng góp mới

- [`CONTRIBUTING.md`](CONTRIBUTING.md) — quy trình đóng góp và kiểm tra.
- [`COMMUNITY.md`](COMMUNITY.md) — các lộ trình tham gia và bậc thang đóng góp.
- [`SUPPORT.md`](SUPPORT.md) — cách yêu cầu hỗ trợ.
- [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) — kỳ vọng về hành vi ứng xử trong cộng đồng.
- [`SECURITY.md`](SECURITY.md) — báo cáo lỗ hổng bảo mật.

### Tìm hiểu hệ thống

- [`docs/WHAT_IS_IDKMESH.md`](docs/WHAT_IS_IDKMESH.md) — tổng quan framework, nghiên cứu, cộng đồng, ứng dụng tham chiếu và các tầng self-hosting.
- [`ITERATION_MODEL.md`](ITERATION_MODEL.md) — từ vựng tiến hóa chuẩn mực và luồng phân quyền.
- [`ARCHITECTURE.md`](ARCHITECTURE.md) — sơ đồ kiến trúc hiện tại.
- [`EVOLUTION.md`](EVOLUTION.md) — chiến lược, nền tảng đã triển khai và các cổng tiếp theo.
- [`ROADMAP.md`](ROADMAP.md) — lộ trình phát triển dựa trên bằng chứng từ trạng thái hiện tại.
- [`docs/README.md`](docs/README.md) — mục lục điều hướng tài liệu.

### Hợp đồng và khả năng tương tác

- [`schemas/README.md`](schemas/README.md) — các hợp đồng máy đọc được hiện tại và quy tắc tạo phiên bản.
- [`docs/specifications/`](docs/specifications/README.md) — chỉ mục đặc tả kỹ thuật/giao thức.
- [`interop/`](interop/) — ranh giới adapter trung lập giao thức, ánh xạ A2A/MCP, ràng buộc danh tính và công cụ kiểm tra chuẩn tương thích.
- [`IDKIPS.md`](IDKIPS.md) — quy trình đề xuất cải tiến lớn cho dự án.

### Nghiên cứu và bằng chứng

- [`docs/research/`](docs/research/README.md) — các chương trình nghiên cứu và bằng chứng.
- [`sim/`](sim/) — mã nguồn mô phỏng/phân tích xác định.
- [`experiments/`](experiments/) — định nghĩa thử nghiệm, bộ điều phối (harnesses) và công cụ phân tích kết quả.
- [`docs/audits/`](docs/audits/) — các cuộc kiểm toán có phạm vi giới hạn và bằng chứng sức khỏe repository.
- [`docs/findings/`](docs/findings/) — các phát hiện kỹ thuật và nghiên cứu.

### Cộng đồng, quản trị và bộ nhớ dự án

- [`GOVERNANCE.md`](GOVERNANCE.md) và [`CONSTITUTION.md`](CONSTITUTION.md) — thẩm quyền và các nguyên tắc được bảo vệ.
- [`COMMUNITY_GROWTH_ENGINE.md`](COMMUNITY_GROWTH_ENGINE.md) — thử nghiệm tăng trưởng cộng đồng ACE và các biện pháp bảo vệ.
- [`PROJECT_RULES.md`](PROJECT_RULES.md) — quy tắc vận hành trên toàn repository.
- [`docs/conversations/`](docs/conversations/README.md) — lịch sử cộng tác có cấu trúc dạng append-only.

## Hồ sơ dự án công khai

Repository này là hồ sơ dự án lâu dài. Các kết luận quan trọng từ công việc dự án phải được đưa vào kiến trúc hiện tại, đặc tả kỹ thuật, quyết định, phát hiện, bằng chứng nghiên cứu, quản trị hoặc mã nguồn triển khai — không để lại trong các kênh chat hoặc bị chôn vùi trong các ghi chú lịch sử.

Các tài liệu lịch sử vẫn có giá trị, nhưng chúng không được âm thầm ghi đè các tài liệu chuẩn mực hiện tại. Xem [`PROJECT_RULES.md`](PROJECT_RULES.md) và [`docs/README.md`](docs/README.md) để biết phân cấp tài liệu.

## Giấy phép

Giấy phép Apache License 2.0. Xem [`LICENSE`](LICENSE).

## Lời mời cộng tác

IDKMesh bắt đầu từ một sự thừa nhận giản dị: **chúng ta chưa biết cách tốt nhất để phối hợp trí tuệ ở quy mô này.**

Nếu bạn có thể cải thiện một câu hỏi, bác bỏ một giả định, tái lập một thử nghiệm, viết một test case, phát hiện một vấn đề bảo mật, làm rõ một hợp đồng, giảm bớt gánh nặng cho người đánh giá, cải thiện quy trình tiếp cận cho người mới, hoặc xây dựng một thành phần đã được xác minh, bạn đều có thể đóng góp.

> **Từ sự không chắc chắn đến trí tuệ tập thể — thông qua bằng chứng.**
