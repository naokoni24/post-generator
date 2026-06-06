(() => {
  const account = ["in", "fo"].join("");
  const host = ["tail", "-tech"].join("") + "." + "jp";
  const address = `${account}@${host}`;

  const contactBody = [
    "お名前：",
    "会社名・店舗名（任意）：",
    "メールアドレス：",
    "電話番号（任意）：",
    "",
    "■ ご相談の種類",
    "□ AI体験コンテンツ",
    "□ 業務効率化・DX支援",
    "□ システム提案・開発",
    "□ AIドキュメント検索システム",
    "□ その他",
    "",
    "■ ご相談内容",
    "（課題やご要望をご自由にお書きください）",
    "",
    "",
    "■ ご希望の対応",
    "□ オンライン相談希望",
    "□ メールでのやり取り希望",
    "□ まずは資料が欲しい",
    "",
    "━━━━━━━━━━━━━━━━━━━━",
    "※通常2営業日以内にご返信いたします。"
  ].join("\n");

  const buildMailto = (kind) => {
    if (kind === "contact") {
      const subject = encodeURIComponent("【Tail Tech】お問い合わせ");
      const body = encodeURIComponent(contactBody);
      return `mailto:${address}?subject=${subject}&body=${body}`;
    }

    return `mailto:${address}`;
  };

  document.querySelectorAll("[data-mail-link]").forEach((link) => {
    const kind = link.getAttribute("data-mail-link") || "plain";
    link.setAttribute("aria-label", "メールを作成する");
    if (kind === "plain") {
      link.textContent = address;
      link.setAttribute("aria-label", `メール：${address}`);
    }
    link.addEventListener("click", (event) => {
      event.preventDefault();
      window.location.href = buildMailto(kind);
    });
  });
})();
