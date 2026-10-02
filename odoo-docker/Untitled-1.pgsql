

SELECT
    m.id                                              AS move_id,
    m.name                                            AS move_name,
    l.sequence,
    l.display_type,
    p.default_code                                    AS product_code,
    COALESCE(t.name->>'vi_VN', t.name->>'en_US')      AS product_name,
    l.name                                            AS label,
    l.line_description,
    l.quantity,
    COALESCE(u.name->>'vi_VN', u.name->>'en_US')      AS uom,
    l.price_unit,
    l.discount,
    ( SELECT string_agg(COALESCE(tx.name->>'vi_VN', tx.name->>'en_US'), ',' ORDER BY tx.sequence, tx.id)
        FROM account_move_line_account_tax_rel r
        JOIN account_tax tx ON tx.id = r.account_tax_id
       WHERE r.account_move_line_id = l.id )          AS taxes,
    a.code_store->>(l.company_id::text)               AS account_code,
    ( SELECT string_agg(COALESCE(aa.name->>'vi_VN', aa.name->>'en_US') || ':' || d.value, ';')
        FROM jsonb_each_text(l.analytic_distribution) d
        CROSS JOIN LATERAL unnest(string_to_array(d.key, ',')) k(aid)
        JOIN account_analytic_account aa ON aa.id = k.aid::int ) AS analytic,
    cur.name                                          AS currency,
    l.price_subtotal,
    l.price_total
FROM account_move_line l
JOIN account_move m          ON m.id = l.move_id
LEFT JOIN product_product p  ON p.id = l.product_id
LEFT JOIN product_template t ON t.id = p.product_tmpl_id
LEFT JOIN uom_uom u          ON u.id = l.product_uom_id
LEFT JOIN account_account a  ON a.id = l.account_id
LEFT JOIN res_currency cur   ON cur.id = l.currency_id
WHERE 1=1
  
  -- and l.move_id = 250
  AND l.display_type IN ('product', 'line_section', 'line_note')
ORDER BY l.sequence, l.id;

--================================== post invoice ==========================

select 
      am.partner_id
      ,'templateSymbol' as templateSymbol -- truyền từ BE
      ,'paymentMethod' as paymentMethod -- double check với hệ thống VNPOST
      , am.currency_id
      , floor(1/am.invoice_currency_rate) as exchangeRate 
      , case 
            when reversed_entry_id is not null
                  or debit_origin_id is not null 
                then 2
            when replacement_origin_id is not null 
                then 3
            else 1 
        end as invoiceType
      ,'taxRate' as taxRate -- double check với hệ thống VNPOST nếu hóa đơn có nhiều tax
      ,am.amount_tax as taxAmount
      ,am.amount_untaxed as totalAmount
      ,am.amount_total as totalPayment
      ,am.invoice_date
      ,'requestId' as requestId -- truyền từ BE UUID - v4
      ,'unitcode' as unitCode  -- get từ API 4.2
      ,'x_external_customer_code' as x_external_customer_code -- Mã khách hàng hệ thống external
      ,'unitName' as unitName -- double check
      ,rp.complete_name as customerName
      ,rp.street as address
      ,rp.phone
      ,rp.email
      ,'cccd' as cccd -- optional
      ,'passport' as passport -- optional
      ,'bankName' as bankName -- optional
      ,'bankAccountNumber' as bankAccountNumber -- optional
      ,'stateBudgetUnitCode' as stateBudgetUnitCode -- optional
      ,'contractId' as contractId -- optional
      ,'isSendEmail' as isSendEmail -- có thể mặc định false
      ,'CreatorCode' as CreatorCode --double check
      ,'CreatorName' as CreatorName  --double check
      ,'issuerCode' as issuerCode --double check
      ,'issuerName' as issuerName --double check
      ,'transactionCode' as transactionCode -- external key for invoice 
      ,'transactionDate' as transactionDate 
      ,'transactionName' as transactionName -- external key for invoice 
      ,'itemType' as itemType  --double check
      ,COALESCE(aml.line_description, aml.name) as itemName
      ,'itemCode' as itemCode
      ,COALESCE(uu.name->>'vi_VN', uu.name->>'en_US') as unit
      ,aml.quantity as quantity
      ,aml.price_unit as unitPrice
      ,'taxRate' as taxRate -- check theo role sản phẩm
      ,'taxType' as taxType -- check theo role sản phẩm
      ,aml.price_total - aml.price_subtotal as taxAmount -- check theo role sản phẩm
      ,aml.price_subtotal as totalAmount -- check theo role sản phẩm
      ,aml.price_total as totalPayment -- check theo role sản phẩm
      ,'discount' as discount -- check theo role sản phẩm
from account_move_line aml
left join account_move am on aml.move_id = am.id
left join res_partner rp on am.partner_id = rp.id
left join uom_uom uu on aml.product_uom_id = uu.id
where display_type = 'product'
      and am.move_type = 'out_invoice'
and am.id = 290
order by aml.id desc;


--=============================== adjust invoice ============================

select 
      case
          when am.debit_origin_id is not null then 1
          when am.reversed_entry_id is not null then 2
          when am.replacement_origin_id is not null then 3
          else 0 -- exception
      end as adjustType
      ,'parentInvoiceKey' as parentInvoiceKey
      



      ,am.partner_id
      ,'templateSymbol' as templateSymbol -- truyền từ BE
      ,'paymentMethod' as paymentMethod -- double check với hệ thống VNPOST
      , am.currency_id
      , COALESCE(floor(1 / NULLIF(am.invoice_currency_rate, 0)), 1) as exchangeRate 
      , case 
            when am.reversed_entry_id is not null
                  or am.debit_origin_id is not null 
                then 2
            when am.replacement_origin_id is not null 
                then 3
            else 1 
        end as invoiceType
      ,'taxRate' as taxRate -- double check với hệ thống VNPOST nếu hóa đơn có nhiều tax
      ,am.amount_tax as taxAmount
      ,am.amount_untaxed as totalAmount
      ,am.amount_total as totalPayment
      ,am.invoice_date
      ,'requestId' as requestId -- truyền từ BE UUID - v4
      ,'unitcode' as unitCode  -- get từ API 4.2
      ,'x_external_customer_code' as x_external_customer_code -- Mã khách hàng hệ thống external
      ,'unitName' as unitName -- double check
      ,rp.complete_name as customerName
      ,rp.street as address
      ,rp.phone
      ,rp.email
      ,'cccd' as cccd -- optional
      ,'passport' as passport -- optional
      ,'bankName' as bankName -- optional
      ,'bankAccountNumber' as bankAccountNumber -- optional
      ,'stateBudgetUnitCode' as stateBudgetUnitCode -- optional
      ,'contractId' as contractId -- optional
      ,'isSendEmail' as isSendEmail -- có thể mặc định false
      ,'CreatorCode' as CreatorCode --double check
      ,'CreatorName' as CreatorName  --double check
      ,'issuerCode' as issuerCode --double check
      ,'issuerName' as issuerName --double check
      ,'transactionCode' as transactionCode -- external key for invoice 
      ,'transactionDate' as transactionDate 
      ,'transactionName' as transactionName -- external key for invoice 
      ,'itemType' as itemType  --double check
      ,COALESCE(aml.line_description, aml.name) as itemName
      ,'itemCode' as itemCode
      ,COALESCE(uu.name->>'vi_VN', uu.name->>'en_US') as unit
      ,aml.quantity as quantity
      ,aml.price_unit as unitPrice
      ,'taxRate' as taxRate -- check theo role sản phẩm
      ,'taxType' as taxType -- check theo role sản phẩm
      ,aml.price_total - aml.price_subtotal as taxAmount -- check theo role sản phẩm
      ,aml.price_subtotal as totalAmount -- check theo role sản phẩm
      ,aml.price_total as totalPayment -- check theo role sản phẩm
      ,'discount' as discount -- check theo role sản phẩm
from account_move_line aml
left join account_move am on aml.move_id = am.id
inner join account_move am2 
      on am2.id = COALESCE(am.reversed_entry_id,
                          am.debit_origin_id,
                          am.replacement_origin_id)
left join res_partner rp on am.partner_id = rp.id
left join uom_uom uu on aml.product_uom_id = uu.id
where display_type = 'product'
      and am.move_type = 'out_invoice'
-- and am.id = 290
order by aml.id desc;






--=============================== replacement invoice ============================

select 
      am2.name as parentInvoiceKey
      ,'agreementDocs' as agreementDocs
      ,'agreementFile' as agreementFile
      ,'agreementSigner' as agreementSigner
      ,'agreementSignerPosition' as agreementSignerPosition
      ,am.adjustment_agreement_date as agreement_date
      ,am.cause
      ,'sellerTaxId' as sellerTaxId
      ,'templateSymbol' as templateSymbol
      ,'paymentMethod' as paymentMethod
      ,rc.name as currencyType -- double check data type input
      ,COALESCE(floor(1 / NULLIF(am.invoice_currency_rate, 0)), 1) as exchangeRate 
      ,case 
            when am.adjustment_type = 'replace' then 3
            when am.adjustment_type in ('decrease','increase') then 2
            when am.adjustment_type is null then 1
            else 0
        end as invoiceType
      ,'taxRate' as taxRate -- double check với hệ thống VNPOST nếu hóa đơn có nhiều tax
      ,am.amount_tax as taxAmount
      ,am.amount_untaxed as totalAmount
      ,am.amount_total as totalPayment
      ,am.invoice_date
      ,'requestId' as requestId -- truyền từ BE UUID - v4
      ,'unitcode' as unitCode  -- get từ API 4.2
      ,'CreatorCode' as CreatorCode --double check
      ,'CreatorName' as CreatorName  --double check
      ,'issuerCode' as issuerCode --double check
      ,'issuerName' as issuerName --double check
      ,'transactionCode' as transactionCode -- external key for invoice 
      ,'transactionDate' as transactionDate 
      ,'transactionName' as transactionName -- external key for invoice 
      ,'x_external_customer_code' as taxId -- Mã khách hàng hệ thống external
      ,'unitName' as unitName -- double check
      ,rp.complete_name as customerName
      ,rp.street as address
      ,rp.phone
      ,rp.email
      ,'cccd' as cccd -- optional
      ,'passport' as passport -- optional
      ,'bankName' as bankName -- optional
      ,'bankAccountNumber' as bankAccountNumber -- optional
      ,'stateBudgetUnitCode' as stateBudgetUnitCode -- optional
      ,'contractId' as contractId -- optional
      ,'isSendEmail' as isSendEmail -- có thể mặc định false
      ,'itemType' as itemType  --double check
      ,COALESCE(aml.line_description, aml.name) as itemName
      ,'itemCode' as itemCode
      ,COALESCE(uu.name->>'vi_VN', uu.name->>'en_US') as unit
      ,aml.quantity as quantity
      ,aml.price_unit as unitPrice
      ,'taxRate' as taxRate -- check theo role sản phẩm
      ,'taxType' as taxType -- check theo role sản phẩm
      ,aml.price_total - aml.price_subtotal as taxAmount -- check theo role sản phẩm
      ,aml.price_subtotal as totalAmount -- check theo role sản phẩm
      ,aml.price_total as totalPayment -- check theo role sản phẩm
      ,'discount' as discount -- check theo role sản phẩm

from account_move_line aml
inner join account_move am on aml.move_id = am.id
inner join account_move am2 
      on am2.id = COALESCE(am.reversed_entry_id,
                          am.debit_origin_id,
                          am.replacement_origin_id)
inner join res_currency rc on am.currency_id = rc.id                          
inner join res_partner rp on am.partner_id = rp.id
inner join uom_uom uu on aml.product_uom_id = uu.id
where display_type = 'product'
      and am.move_type = 'out_invoice'
-- and am.id = 290
order by aml.id desc;












