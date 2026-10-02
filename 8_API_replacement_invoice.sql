
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
      ,am.currency_id as currencyType -- double check data type input
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
inner join res_partner rp on am.partner_id = rp.id
inner join uom_uom uu on aml.product_uom_id = uu.id
where display_type = 'product'
      and am.move_type = 'out_invoice'
-- and am.id = 290
order by aml.id desc;