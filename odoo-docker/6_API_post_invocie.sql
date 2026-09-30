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
      ,aml.line_description as itemName
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
order by aml.id desc
