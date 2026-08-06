-- User Roles Table
CREATE TABLE user_role (
    role_id INT IDENTITY(1,1) PRIMARY KEY,
    role_name VARCHAR(100) NOT NULL UNIQUE,
    is_active BIT NOT NULL DEFAULT 1,
	created_date DATETIME DEFAULT GETDATE(),
    modified_date DATETIME DEFAULT GETDATE()
);

INSERT INTO user_role (role_name)
VALUES
    ('Ideation Requestor'),
    ('Data Science Programmer'),
    ('Manager'),
    ('QA'),
    ('Viewer'),
    ('Operations'),
    ('Admin');

-- Users Table
CREATE TABLE users (
    id INT IDENTITY(1,1) PRIMARY KEY,
    username VARCHAR(100) NOT NULL UNIQUE,
    hashed_password VARCHAR(255),
    name VARCHAR(255) NOT NULL,
    is_active BIT NOT NULL DEFAULT 1,
    created_at DATETIME NOT NULL DEFAULT GETDATE(),
    modified_at DATETIME NULL
);

-- User Access Table
CREATE TABLE user_access (
    user_id INT NOT NULL,
    role_id INT NOT NULL,
    is_active BIT NOT NULL DEFAULT 1,
    created_date DATETIME NOT NULL DEFAULT GETDATE(),
    modified_date DATETIME NOT NULL DEFAULT GETDATE(),

    CONSTRAINT PK_user_access
        PRIMARY KEY (user_id, role_id),

    CONSTRAINT FK_user_access_user
        FOREIGN KEY (user_id)
        REFERENCES users(id),

    CONSTRAINT FK_user_access_role
        FOREIGN KEY (role_id)
        REFERENCES user_role(role_id)
);

-- =====================================================
-- 1. CONCEPT KEYS (anchor table � created first)
-- =====================================================
CREATE TABLE ConceptKeys (
    ConceptId          VARCHAR(50) NOT NULL PRIMARY KEY,
	CurrentConceptId   VARCHAR(50) NULL,
    ClientCode         VARCHAR(10) NULL,       -- e.g. MRW
    MasterConceptId    VARCHAR(10) NULL,       -- e.g. 0000
    ReviewType         CHAR(1) NULL,           -- e.g. A
    ClaimType          CHAR(1) NULL,           -- e.g. P
    Edition            INT NULL,               -- e.g. 1 (formatted as 001)
    Version            INT NULL,               -- e.g. 1 (formatted as 001 or D001)
    IsDevelopment      BIT NOT NULL DEFAULT 1, -- 1 = Development (D-prefix), 0 = Production
    RunNumber          INT NULL,               -- e.g. 1 (formatted as 001), set only in Production
    CreatedDate        DATETIME NOT NULL DEFAULT GETDATE(),
    UpdatedDate        DATETIME NULL
);

-- =====================================================
-- 2. CONCEPTS (final/main concept data)
-- =====================================================
CREATE TABLE Concepts (
    ConceptId VARCHAR(50) NOT NULL PRIMARY KEY,
    ConceptName VARCHAR(255) NOT NULL,
    DevelopmentStatus VARCHAR(50),
    Priority VARCHAR(50),
    HaloNumber VARCHAR(100),
    InternalConceptDescription NVARCHAR(MAX),
    EstimatedVolume INT,
    EstimatedDollars DECIMAL(18,2),
    ConfidenceScore VARCHAR(20),
    IdeationRequestorId INT,
    DataScienceProgrammerId INT,
    PreviousReportId VARCHAR(100),
    QASchedule DATETIME,
    ProductionSchedule DATETIME,
    Createdby INT NOT NULL,
    CreatedDate DATETIME DEFAULT GETDATE(),
    UpdatedDate DATETIME DEFAULT GETDATE(),
    DevelopmentCompleted BIT DEFAULT 0,
    ClientApprovalCompleted BIT DEFAULT 0,
    SupportingDocumentsCompleted BIT DEFAULT 0,
    CONSTRAINT FK_Concepts_Keys
        FOREIGN KEY (ConceptId)
        REFERENCES ConceptKeys(ConceptId)
);

-- =====================================================
-- 3. CONCEPT DRAFTS (draft concept data)
-- =====================================================
CREATE TABLE ConceptDrafts (
    DraftId INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    ConceptId VARCHAR(50) NOT NULL,
    ConceptName VARCHAR(255) NOT NULL,
    DevelopmentStatus VARCHAR(50),
    Priority VARCHAR(50),
    HaloNumber VARCHAR(100),
    InternalConceptDescription NVARCHAR(MAX),
    EstimatedVolume INT,
    EstimatedDollars DECIMAL(18,2),
    ConfidenceScore VARCHAR(20),
    IdeationRequestorId INT,
    DataScienceProgrammerId INT,
    PreviousReportId VARCHAR(100),
    QASchedule DATETIME,
    ProductionSchedule DATETIME,
    DevelopmentCompleted BIT DEFAULT 0,
    ClientApprovalCompleted BIT DEFAULT 0,
    SupportingDocumentsCompleted BIT DEFAULT 0,
    IsActive BIT DEFAULT 1,
    Createdby INT NOT NULL,
    CreatedDate DATETIME DEFAULT GETDATE(),
    UpdatedDate DATETIME DEFAULT GETDATE(),
    CONSTRAINT FK_ConceptDrafts_Keys
        FOREIGN KEY (ConceptId)
        REFERENCES ConceptKeys(ConceptId)
);

-- =====================================================
-- 4. CONCEPT DEVELOPMENT NOTES
-- =====================================================
CREATE TABLE ConceptDevelopmentNotes (
    NoteId INT IDENTITY(1,1) PRIMARY KEY,
    ConceptId VARCHAR(50) NOT NULL,
    NoteText NVARCHAR(MAX),
    Createdby INT NOT NULL,
    RoleId INT NULL,
    CreatedDate DATETIME DEFAULT GETDATE(),
    CONSTRAINT FK_ConceptDevelopmentNotes_Keys
        FOREIGN KEY (ConceptId)
        REFERENCES ConceptKeys(ConceptId)
);

-- =====================================================
-- 5. CONCEPT ATTACHMENTS
-- =====================================================
CREATE TABLE ConceptAttachments (
    AttachmentId INT IDENTITY(1,1) PRIMARY KEY,
    ConceptId VARCHAR(50) NOT NULL,
    AttachmentType VARCHAR(20),
	DocIndex INT NULL,
	DocName VARCHAR(255) NULL,
    FileName VARCHAR(255),
    FilePath VARCHAR(500),
    FileSize BIGINT,
	sourceurl VARCHAR(255),
    Createdby INT NOT NULL,
	UpdatedBy INT NULL,
    UpdatedDate DATETIME NULL,
    Version INT DEFAULT 1,
    IsActive BIT DEFAULT 1,
    UploadedOn DATETIME DEFAULT GETDATE(),
    CONSTRAINT FK_ConceptAttachments_Keys
        FOREIGN KEY (ConceptId)
        REFERENCES ConceptKeys(ConceptId)
);



-- =====================================================
-- 6. CLIENT APPROVAL
-- =====================================================
CREATE TABLE ClientApproval (
    ApprovalId INT IDENTITY(1,1) PRIMARY KEY,
    ConceptId VARCHAR(50) NOT NULL,
    ConceptName VARCHAR(50),
    ClientConceptName VARCHAR(255),
    ClientConceptDescription NVARCHAR(MAX),
    ClientApprovalStatus VARCHAR(50),
    SubmittedToClientOn DATETIME,
    ClientApprovalNotes NVARCHAR(MAX),
	EstimatedVolume INT,
	EstimatedDollars DECIMAL(18,2),
    Approvedby INT NULL,
    IsActive BIT DEFAULT 1,
    CreatedDate DATETIME DEFAULT GETDATE(),
    UpdatedDate DATETIME DEFAULT GETDATE(),
    CONSTRAINT FK_ClientApproval_Keys
        FOREIGN KEY (ConceptId)
        REFERENCES ConceptKeys(ConceptId)
);


-- =====================================================
-- 7. SUPPORTING DOCUMENTS
-- =====================================================
CREATE TABLE SupportingDocuments (
    DocumentId INT IDENTITY(1,1) PRIMARY KEY,
    ConceptId VARCHAR(50) NOT NULL,
    DocumentName VARCHAR(255),
    DocumentUrl VARCHAR(1000),
    FileName VARCHAR(255),
    FilePath VARCHAR(500),
    Createdby INT NOT NULL,
    UploadedOn DATETIME DEFAULT GETDATE(),
    CONSTRAINT FK_SupportingDocuments_Keys
        FOREIGN KEY (ConceptId)
        REFERENCES ConceptKeys(ConceptId)
);


--concept id table creation 

-- 1. Clients Table
CREATE TABLE clients (
    client_id VARCHAR(50) PRIMARY KEY,
    client_name VARCHAR(255) NOT NULL,
    description VARCHAR(255),
	claim_other VARCHAR(255),
    createdby VARCHAR(100),
    createddate DATETIME DEFAULT GETDATE(),
    modifieddate DATETIME NULL,
    active BIT DEFAULT 1
);

-- 2. Master Concepts Table
CREATE TABLE master_concepts (
    master_id VARCHAR(20) PRIMARY KEY,   
    concept_name VARCHAR(255) NOT NULL,
    description VARCHAR(255),
	example VARCHAR(255),
    createdby VARCHAR(100),
    createddate DATETIME DEFAULT GETDATE(),
    modifieddate DATETIME NULL,
    active BIT DEFAULT 1
);

-- 3. Review Type Table
CREATE TABLE review_type (
    review_type VARCHAR(20) PRIMARY KEY,  
    description VARCHAR(255) NOT NULL,
    createdby VARCHAR(100),
    createddate DATETIME DEFAULT GETDATE(),
    modifieddate DATETIME NULL,
    active BIT DEFAULT 1
);

-- 4. Claim Type Table
CREATE TABLE claim_type (
    claim_type VARCHAR(20) PRIMARY KEY,  
    description VARCHAR(255) NOT NULL,
    createdby VARCHAR(100),
    createddate DATETIME DEFAULT GETDATE(),
    modifieddate DATETIME NULL,
    active BIT DEFAULT 1
);


CREATE TABLE development_status(
    id INT IDENTITY(1,1) PRIMARY KEY,
    value VARCHAR(50) NOT NULL,
    created_date DATETIME DEFAULT GETDATE()
);

CREATE TABLE priority_status(
    id INT IDENTITY(1,1) PRIMARY KEY,
    value VARCHAR(50) NOT NULL,
    created_date DATETIME DEFAULT GETDATE()
);

CREATE TABLE ClientApproval_status(
    id INT IDENTITY(1,1) PRIMARY KEY,
    value VARCHAR(50) NOT NULL,
    created_date DATETIME DEFAULT GETDATE()
)

-- Insert statements

INSERT INTO clients
(client_id, client_name, description, claim_other, createdby, active)
VALUES
('CSP','UHC C&S','UnitedHealthcare''s Community & State Plans','Facets','system',1),
('HCP','UHC H&C','UnitedHealthcare''s Home & Community Plans','COSMOS','system',1),
('HUM','Humana','','','system',1),
('IFP','UHC C&I','UnitedHealthcare''s Exchange Plans','Facets','system',1),
('MRW','MedReview (Master Rules)','Internal "Library" of Concepts','MedMine','system',1),
('P3X','P3','','','system',1),
('UMR','UMR','ASO self-funded employer groups who have purchased PI services as an add-on to ASO services',
'Partner Portal for claim lookup; claim processing system is CPS.','system',1);

INSERT INTO development_status (value)
VALUES 
('New'), 
('Programming Queue'), 
('Programming'), 
('Result Set QA'), 
('QA Revise'), 
('Researching'), 
('Approved'), 
('Client Review'), 
('Client Approved'), 
('Client Revise'), 
('Client Denied'), 
('Client Resubmit'), 
('Pre-Production'), 
('Production'), 
('Closed'), 
('Hold'), 
('Revisit'), 
('Superseded'); 

INSERT INTO master_concepts
(master_id, concept_name, description, example, createdby, active)
VALUES
('0000','Code Pairs','Code pairs not allowed together. Unbundling.','NCCI, DME Unbundling, Image Guidance Unbundling.','system',1),
('0001','Consolidated Billing','Services included in the payment to another entity under arrangement, like SNF or home health.','SNF or Home Health Consolidated Billing.','system',1),
('0002','Correct Coding','Codes are used incorrectly or are missing.','Add-on Codes, Co-Surgeon w/o Modifier 62, Mohs.','system',1),
('0003','Duplicates','Duplicate payments issued.','Duplicates.','system',1),
('0004','E&M Payment Errors','The E&M service is paid incorrectly because it is incorrectly coded, or is included in another service, but is not Global Days.','Anesthesia w/ E&M, Hospital D/C Management, Preventive Medicine and E&M.','system',1),
('0005','Eligibility','No member eligibility for the DOS.','Term date.','system',1),
('0006','Frequency','Services paid more frequently than allowed.','AWV per Year, Reasonable Useful Lifetime, Date Span Codes, Per Diem Codes.','system',1),
('0007','Global Services','Services included in the global period of other services.','Global Days, TCM During the Global Period.','system',1),
('0008','Hospice and Related Services','Any/all services related to and/or included in Hospice care.','Ambulance, DME, Outpatient During Hospice.','system',1),
('0009','Inclusive to Facility Charges','Services that are included in the payment to a facility.','TC During Inpatient, Pre-admission Testing/3-Day Rule, Outpatient During Inpatient','system',1),
('0010','Non-Covered','Services that are not allowed per policy, and are not member responsibility.','Assistant/C-Surgeon Not Allowed, CPAP without OSA, CPM without Total Knee.','system',1),
('0011','OPPS Rules','OPPS edits and rules.','Status Indicator J1','system',1),
('0012','Pricing - Anesthesia','Pricing errors/rules for anesthesia claims.','OB Anesthesia, Modifiers QK, QX, QY','system',1),
('0013','Pricing - DME','Pricing errors/rules for DME claims.','DME Capped Rental, Overlapping Span Dates.','system',1),
('0014','Pricing - DRG','Pricing errors/rules for DRG claims.','Incorrect Discharge Status, Readmissions.','system',1),
('0015','Pricing - Inpatient','Pricing errors/rules for inpatient claims without specifically being DRG related.','Corrected Claims, Interim Bills, Mom & Baby, Never Events.','system',1),
('0016','Pricing - Medical Drugs','Pricing errors/rules for medical drug claims.','None yet.','system',1),
('0017','Pricing - Non-Surgery','Pricing errors/rules for professional claims that are not specifically related to multiple surgery rules.','Inherently Bilateral, Global vs. PC/TC Duplicates.','system',1),
('0018','Pricing - Outpatient','Pricing errors/rules for outpatient facility claims.','Revenue Code to Procedure Code, ASC Ancillary Services.','system',1),
('0019','Pricing - SNF','Pricing errors/rules for SNF claims.','SNF Qualifying Stay.','system',1),
('0020','Pricing - Surgery','Pricing errors/rules for professional surgery claims.','Split Surgery Packages, Multiple Surgery Reduction (also, Assistant/Co-Surgeons.)','system',1),
('0021','Pricing - Dental','Pricing errors/rules for dental claims.','None yet.','system',1),
('0022','Medical Drugs','Medical drugs not paid per policy or FDA guidelines.','Neulasta the Same Day as Chemotherapy.','system',1),
('0023','Units','Units billed are greater than allowed.','MUE, CT/MRI Scan Excessive Units.','system',1),
('0024','Medical Necessity','Review of the medical necessity for the services billed.','Short-stay inpatient claims. DME for lower limb prosthetics. Genetic testing.','system',1),
('0025','Readmissions','Inpatient readmissions billed as separate stays.','Inpatient readmissions billed as separate stays.','system',1),
('0026','Pricing - General','Pricing errors/rules for assorted claims.','Charge Amount Equals Allowed Amount','system',1),
('0027','Incorrect Contract Rate','Not paid according to contract language.','Wrong conversion factor loaded in the system, wrong DRG version','system',1),
('0100','SCOPE Only','Only for pulling data not yet tied to a Data Mining Concept. Will never be used for Production.','','system',1);

INSERT INTO review_type
(review_type, description, createdby, active)
VALUES
('A','Automated (Data Mining)','system',1),
('B','Hospital Bill Audit','system',1),
('C','Coding (non-DRG)','system',1),
('D','DRG Validation','system',1),
('H','Hybrid (DM to CR)','system',1),
('L','Length of Stay','system',1),
('M','Medical Necessity','system',1),
('P','Provider Specific','system',1),
('R','Prescription','system',1),
('S','Semi-Automated','system',1),
('X','SCOPE Data','system',1);

INSERT INTO claim_type
(claim_type, description, createdby, active)
VALUES
('A','ALL','system',1),
('C','Orthotics','system',1),
('D','DME','system',1),
('F','Facility (all UB-02 claims, depending on mapping)','system',1),
('H','Hospice','system',1),
('I','Inpatient','system',1),
('L','Laboratory / Pathology','system',1),
('M','Ambulance','system',1),
('N','Ancillary','system',1),
('O','Outpatient','system',1),
('P','Professional (all CMS-1500 claims, depending on mapping)','system',1),
('R','Prescription','system',1),
('S','SNF','system',1),
('T','Dental','system',1);

INSERT INTO priority_status (value)
VALUES
('High'),
('Low'),
('Medium');

INSERT INTO ClientApproval_status (value)
VALUES
('Submitted'),
('Approved'),
('Rejected');