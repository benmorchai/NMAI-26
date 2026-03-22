# Tripletex API Reference (from OpenAPI spec)

## /employee
  /employee [GET, POST]
  /employee/category [GET, POST]
  /employee/category/list [PUT, POST, DELETE]
  /employee/category/{id} [GET, PUT, DELETE]
  /employee/employment [GET, POST]
  /employee/employment/details [GET, POST]
  /employee/employment/details/{id} [GET, PUT]
  /employee/employment/employmentType [GET]
  /employee/employment/employmentType/employmentEndReasonType [GET]
  /employee/employment/employmentType/employmentFormType [GET]
  /employee/employment/employmentType/maritimeEmploymentType [GET]
  /employee/employment/employmentType/salaryType [GET]
  /employee/employment/employmentType/scheduleType [GET]
  /employee/employment/leaveOfAbsence [GET, POST]
  /employee/employment/leaveOfAbsence/list [POST]
  /employee/employment/leaveOfAbsence/{id} [GET, PUT]
  /employee/employment/leaveOfAbsenceType [GET]
  /employee/employment/occupationCode [GET]
  /employee/employment/occupationCode/{id} [GET]
  /employee/employment/remunerationType [GET]

## /customer
  /customer [GET, POST]
  /customer/category [GET, POST]
  /customer/category/{id} [GET, PUT]
  /customer/list [PUT, POST]
  /customer/{id} [GET, PUT, DELETE]

## /supplier
  /supplier [GET, POST]
  /supplier/list [PUT, POST]
  /supplier/{id} [GET, PUT, DELETE]

## /product
  /product [GET, POST]
  /product/discountGroup [GET]
  /product/discountGroup/{id} [GET]
  /product/external [GET]
  /product/external/{id} [GET]
  /product/group [GET, POST]
  /product/group/list [PUT, POST, DELETE]
  /product/group/query [GET]
  /product/group/{id} [GET, PUT, DELETE]
  /product/groupRelation [GET, POST]
  /product/groupRelation/list [POST, DELETE]
  /product/groupRelation/{id} [GET, DELETE]
  /product/inventoryLocation [GET, POST]
  /product/inventoryLocation/list [PUT, POST]
  /product/inventoryLocation/{id} [GET, PUT, DELETE]
  /product/list [PUT, POST]
  /product/logisticsSettings [GET, PUT]
  /product/productPrice [GET]
  /product/supplierProduct [GET, POST]
  /product/supplierProduct/getSupplierProductsByIds [POST]

## /department
  /department [GET, POST]
  /department/list [PUT, POST]
  /department/query [GET]
  /department/{id} [GET, PUT, DELETE]

## /project
  /project [GET, POST, DELETE]
  /project/>forTimeSheet [GET]
  /project/batchPeriod/budgetStatusByProjectIds [GET]
  /project/batchPeriod/invoicingReserveByProjectIds [GET]
  /project/category [GET, POST]
  /project/category/{id} [GET, PUT]
  /project/controlForm [GET]
  /project/controlForm/{id} [GET]
  /project/controlFormType [GET]
  /project/controlFormType/{id} [GET]
  /project/dynamicControlForm/{id}/:copyFieldValuesFromLastEditedForm [PUT]
  /project/hourlyRates [GET, POST]
  /project/hourlyRates/deleteByProjectIds [DELETE]
  /project/hourlyRates/list [PUT, POST, DELETE]
  /project/hourlyRates/projectSpecificRates [GET, POST]
  /project/hourlyRates/projectSpecificRates/list [PUT, POST, DELETE]
  /project/hourlyRates/projectSpecificRates/{id} [GET, PUT, DELETE]
  /project/hourlyRates/updateOrAddHourRates [PUT]
  /project/hourlyRates/{id} [GET, PUT, DELETE]
  /project/import [POST]

## /invoice
  /invoice [GET, POST]
  /invoice/details [GET]
  /invoice/details/{id} [GET]
  /invoice/list [POST]
  /invoice/paymentType [GET]
  /invoice/paymentType/{id} [GET]
  /invoice/{id} [GET]
  /invoice/{id}/:createCreditNote [PUT]
  /invoice/{id}/:createReminder [PUT]
  /invoice/{id}/:payment [PUT]
  /invoice/{id}/:send [PUT]
  /invoice/{invoiceId}/pdf [GET]

## /order
  /order [GET, POST]
  /order/:invoiceMultipleOrders [PUT]
  /order/list [POST]
  /order/orderConfirmation/{orderId}/pdf [GET]
  /order/orderGroup [GET, PUT, POST]
  /order/orderGroup/{id} [GET, DELETE]
  /order/orderline [POST]
  /order/orderline/list [POST]
  /order/orderline/orderLineTemplate [GET]
  /order/orderline/{id} [GET, PUT, DELETE]
  /order/orderline/{id}/:pickLine [PUT]
  /order/orderline/{id}/:unpickLine [PUT]
  /order/packingNote/{orderId}/pdf [GET]
  /order/sendInvoicePreview/{orderId} [PUT]
  /order/sendOrderConfirmation/{orderId} [PUT]
  /order/sendPackingNote/{orderId} [PUT]
  /order/{id} [GET, PUT, DELETE]
  /order/{id}/:approveSubscriptionInvoice [PUT]
  /order/{id}/:attach [PUT]
  /order/{id}/:invoice [PUT]

## /ledger
  /ledger [GET]
  /ledger/account [GET, POST]
  /ledger/account/list [PUT, POST, DELETE]
  /ledger/account/{id} [GET, PUT, DELETE]
  /ledger/accountingDimensionName [GET, POST]
  /ledger/accountingDimensionName/search [GET]
  /ledger/accountingDimensionName/{id} [GET, PUT, DELETE]
  /ledger/accountingDimensionValue [POST]
  /ledger/accountingDimensionValue/list [PUT]
  /ledger/accountingDimensionValue/search [GET]
  /ledger/accountingDimensionValue/{id} [GET, DELETE]
  /ledger/accountingPeriod [GET]
  /ledger/accountingPeriod/{id} [GET]
  /ledger/annualAccount [GET]
  /ledger/annualAccount/{id} [GET]
  /ledger/closeGroup [GET]
  /ledger/closeGroup/{id} [GET]
  /ledger/openPost [GET]
  /ledger/paymentTypeOut [GET, POST]
  /ledger/paymentTypeOut/list [PUT, POST]

## /travelExpense
  /travelExpense [GET, POST]
  /travelExpense/:approve [PUT]
  /travelExpense/:copy [PUT]
  /travelExpense/:createVouchers [PUT]
  /travelExpense/:deliver [PUT]
  /travelExpense/:unapprove [PUT]
  /travelExpense/:undeliver [PUT]
  /travelExpense/accommodationAllowance [GET, POST]
  /travelExpense/accommodationAllowance/{id} [GET, PUT, DELETE]
  /travelExpense/cost [GET, POST]
  /travelExpense/cost/list [PUT]
  /travelExpense/cost/{id} [GET, PUT, DELETE]
  /travelExpense/costCategory [GET]
  /travelExpense/costCategory/{id} [GET]
  /travelExpense/costParticipant [POST]
  /travelExpense/costParticipant/createCostParticipantAdvanced [POST]
  /travelExpense/costParticipant/list [POST, DELETE]
  /travelExpense/costParticipant/{costId}/costParticipants [GET]
  /travelExpense/costParticipant/{id} [GET, DELETE]
  /travelExpense/drivingStop [POST]

## /activity
  /activity [GET, POST]
  /activity/>forTimeSheet [GET]
  /activity/list [POST]
  /activity/{id} [GET]

## /timesheet
  /timesheet/allocated [GET, POST]
  /timesheet/allocated/:approveList [PUT]
  /timesheet/allocated/:unapproveList [PUT]
  /timesheet/allocated/list [PUT, POST]
  /timesheet/allocated/{id} [GET, PUT, DELETE]
  /timesheet/allocated/{id}/:approve [PUT]
  /timesheet/allocated/{id}/:unapprove [PUT]
  /timesheet/companyHoliday [GET, POST]
  /timesheet/companyHoliday/{id} [GET, PUT, DELETE]
  /timesheet/entry [GET, POST]
  /timesheet/entry/>recentActivities [GET]
  /timesheet/entry/>recentProjects [GET]
  /timesheet/entry/>totalHours [GET]
  /timesheet/entry/list [PUT, POST]
  /timesheet/entry/{id} [GET, PUT, DELETE]
  /timesheet/month/:approve [PUT]
  /timesheet/month/:complete [PUT]
  /timesheet/month/:reopen [PUT]
  /timesheet/month/:unapprove [PUT]
  /timesheet/month/byMonthNumber [GET]

## /contact
  /contact [GET, POST]
  /contact/list [POST, DELETE]
  /contact/{id} [GET, PUT]

## /incomingInvoice
  /incomingInvoice [POST]
  /incomingInvoice/search [GET]
  /incomingInvoice/{voucherId} [GET, PUT]
  /incomingInvoice/{voucherId}/addPayment [POST]

## /salary
  /salary/compilation [GET]
  /salary/compilation/pdf [GET]
  /salary/financeTax/reconciliation/context [POST]
  /salary/financeTax/reconciliation/{reconciliationId}/overview [GET]
  /salary/financeTax/reconciliation/{reconciliationId}/paymentsOverview [GET]
  /salary/holidayAllowance/reconciliation/context [POST]
  /salary/holidayAllowance/reconciliation/{reconciliationId}/holidayAllowanceDetails [GET]
  /salary/holidayAllowance/reconciliation/{reconciliationId}/holidayAllowanceSummary [GET]
  /salary/mandatoryDeduction/reconciliation/context [POST]
  /salary/mandatoryDeduction/reconciliation/{reconciliationId}/overview [GET]
  /salary/mandatoryDeduction/reconciliation/{reconciliationId}/paymentsOverview [GET]
  /salary/payrollTax/reconciliation/context [POST]
  /salary/payrollTax/reconciliation/{reconciliationId}/overview [GET]
  /salary/payrollTax/reconciliation/{reconciliationId}/paymentsOverview [GET]
  /salary/payslip [GET]
  /salary/payslip/{id} [GET]
  /salary/payslip/{id}/pdf [GET]
  /salary/settings [GET, PUT]
  /salary/settings/holiday [GET, POST]
  /salary/settings/holiday/list [PUT, POST, DELETE]

## /bank
  /bank [GET]
  /bank/reconciliation [GET, POST]
  /bank/reconciliation/>last [GET]
  /bank/reconciliation/>lastClosed [GET]
  /bank/reconciliation/closedWithUnmatchedTransactions [GET]
  /bank/reconciliation/match [GET, POST]
  /bank/reconciliation/match/:suggest [PUT]
  /bank/reconciliation/match/count [GET]
  /bank/reconciliation/match/query [GET]
  /bank/reconciliation/match/{id} [GET, PUT, DELETE]
  /bank/reconciliation/matches/counter [GET, POST]
  /bank/reconciliation/paymentType [GET]
  /bank/reconciliation/paymentType/{id} [GET]
  /bank/reconciliation/settings [GET, POST]
  /bank/reconciliation/settings/{id} [PUT]
  /bank/reconciliation/transactions/unmatched:csv [PUT]
  /bank/reconciliation/{id} [GET, PUT, DELETE]
  /bank/reconciliation/{id}/:adjustment [PUT]
  /bank/statement [GET]
  /bank/statement/import [POST]

## /currency
  /currency [GET]
  /currency/{fromCurrencyID}/exchangeRate [GET]
  /currency/{fromCurrencyID}/{toCurrencyID}/exchangeRate [GET]
  /currency/{id} [GET]
  /currency/{id}/rate [GET]

## Key Schemas

### Employee
  id: integer
  version: integer
  firstName: string
  lastName: string
  employeeNumber: string
  dateOfBirth: string
  email: string
  phoneNumberMobileCountry: Country
  phoneNumberMobile: string
  phoneNumberHome: string
  phoneNumberWork: string
  nationalIdentityNumber: string
  dnumber: string
  internationalId: InternationalId
  bankAccountNumber: string
  iban: string
  bic: string
  creditorBankCountryId: integer
  usesAbroadPayment: boolean
  userType: string

### Customer
  id: integer
  version: integer
  name: string
  organizationNumber: string
  globalLocationNumber: integer
  supplierNumber: integer
  customerNumber: integer
  isSupplier: boolean
  isInactive: boolean
  accountManager: Employee
  department: Department
  email: string
  invoiceEmail: string
  overdueNoticeEmail: string
  bankAccounts: array
  phoneNumber: string
  phoneNumberMobile: string
  description: string
  language: string
  displayName: string

### Supplier
  id: integer
  version: integer
  name: string
  organizationNumber: string
  supplierNumber: integer
  customerNumber: integer
  isCustomer: boolean
  isInactive: boolean
  email: string
  bankAccounts: array
  invoiceEmail: string
  overdueNoticeEmail: string
  phoneNumber: string
  phoneNumberMobile: string
  description: string
  isPrivateIndividual: boolean
  showProducts: boolean
  accountManager: Employee
  postalAddress: Address
  physicalAddress: Address

### Product
  id: integer
  version: integer
  name: string
  number: string
  description: string
  orderLineDescription: string
  ean: string
  costExcludingVatCurrency: number
  expenses: number
  priceExcludingVatCurrency: number
  priceIncludingVatCurrency: number
  isInactive: boolean
  discountGroup: DiscountGroup
  productUnit: ProductUnit
  isStockItem: boolean
  vatType: VatType
  currency: Currency
  department: Department
  account: Account
  supplier: Supplier

### Department
  id: integer
  version: integer
  name: string
  departmentNumber: string
  departmentManager: Employee
  isInactive: boolean

### Project
  id: integer
  version: integer
  name: string
  number: string
  description: string
  projectManager: Employee
  department: Department
  mainProject: Project
  startDate: string
  endDate: string
  customer: Customer
  isClosed: boolean
  isReadyForInvoicing: boolean
  isInternal: boolean
  isOffer: boolean
  isFixedPrice: boolean
  projectCategory: ProjectCategory
  deliveryAddress: Address
  boligmappaAddress: Address
  displayNameFormat: string

### Invoice
  id: integer
  version: integer
  invoiceNumber: integer
  invoiceDate: string
  customer: Customer
  invoiceDueDate: string
  kid: string
  comment: string
  orders: array
  voucher: Voucher
  currency: Currency
  invoiceRemarks: string
  invoiceRemark: InvoiceRemark
  paymentTypeId: integer
  paidAmount: number
  ehfSendStatus: string

### Order
  id: integer
  version: integer
  customer: Customer
  contact: Contact
  attn: Contact
  receiverEmail: string
  overdueNoticeEmail: string
  number: string
  reference: string
  ourContact: Contact
  ourContactEmployee: Employee
  department: Department
  orderDate: string
  project: Project
  invoiceComment: string
  internalComment: string
  currency: Currency
  invoicesDueIn: integer
  status: string
  invoicesDueInType: string

### OrderLine
  id: integer
  version: integer
  product: Product
  inventory: Inventory
  inventoryLocation: InventoryLocation
  description: string
  count: number
  unitCostCurrency: number
  unitPriceExcludingVatCurrency: number
  currency: Currency
  markup: number
  discount: number
  vatType: VatType
  vendor: Company
  order: Order
  unitPriceIncludingVatCurrency: number
  isSubscription: boolean
  subscriptionPeriodStart: string
  subscriptionPeriodEnd: string
  orderGroup: OrderGroup

### Voucher
  id: integer
  version: integer
  date: string
  description: string
  voucherType: VoucherType
  reverseVoucher: Voucher
  postings: array
  document: Document
  attachment: Document
  externalVoucherNumber: string
  ediDocument: Document
  vendorInvoiceNumber: string

### Posting
  id: integer
  version: integer
  voucher: Voucher
  date: string
  description: string
  account: Account
  amortizationAccount: Account
  amortizationStartDate: string
  amortizationEndDate: string
  customer: Customer
  supplier: Supplier
  employee: Employee
  project: Project
  product: Product
  department: Department
  vatType: VatType
  amount: number
  amountCurrency: number
  amountGross: number
  amountGrossCurrency: number

### Contact
  id: integer
  version: integer
  firstName: string
  lastName: string
  displayName: string
  email: string
  phoneNumberMobileCountry: Country
  phoneNumberMobile: string
  phoneNumberWork: string
  customer: Customer
  department: Department
  isInactive: boolean

### TravelExpense
  id: integer
  version: integer
  attestationSteps: array
  attestation: Attestation
  project: Project
  employee: Employee
  approvedBy: Employee
  completedBy: Employee
  rejectedBy: Employee
  department: Department
  freeDimension1: AccountingDimensionValue
  freeDimension2: AccountingDimensionValue
  freeDimension3: AccountingDimensionValue
  payslip: Payslip
  vatType: VatType
  paymentCurrency: Currency
  travelDetails: TravelDetails
  voucher: Voucher
  attachment: Document
  isChargeable: boolean

### Activity
  id: integer
  version: integer
  name: string
  number: string
  description: string
  activityType: string
  isChargeable: boolean
  rate: number
  costPercentage: number
  displayName: string

