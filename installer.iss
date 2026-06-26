; ==============================================================================
; 1. AVVIOPC PRINT DAEMON - INNO SETUP CORE AND LANGUAGE SCRIPT
; ==============================================================================

[Setup]
AppId={{A1B2C3D4-E5F6-7890-1234-56789ABCDEF0}
AppName=AvvioPC Print Daemon
AppVersion=2.0
; Absolute deployment directory to bypass restrictive corporate group policies
DefaultDirName=C:\AvvioPC\Print_Daemon
DefaultGroupName=AvvioPC

; Reactivate welcome screen and bind the main vertical splash artwork (164x314 px .bmp)
DisableWelcomePage=no
WizardImageFile=welcome_splash.bmp
WizardStyle=modern
DisableProgramGroupPage=yes

; Install in User-Space to bypass Admin rights
PrivilegesRequired=lowest
OutputDir=userdocs:InnoSetupOutput
OutputBaseFilename=Install_AvvioPC_Daemon
Compression=lzma
SolidCompression=yes

[Languages]
; Official Italian language pack integration
Name: "italian"; MessagesFile: "compiler:Languages\Italian.isl"

[Messages]
WelcomeLabel1=Benvenuto nel setup di%nAvvioPC Print Daemon
WelcomeLabel2=Questo programma installerà il motore di stampa invisibile per il Servizio Avvio PC sul tuo computer.%n%nIl demone funzionera' silenziosamente in background e configurerà in automatico i layout da stampare.%n%nClicca su Avanti per selezionare il tuo punto vendita e continuare.

; ==============================================================================
; 2. FILES, ICONS AND EXECUTION CONFIGURATION
; ==============================================================================

[Files]
; Relative path: PyInstaller outputs the executable inside the "dist" subfolder
Source: "dist\print_daemon.exe"; DestDir: "{app}"; Flags: ignoreversion

; Relative path: These bitmaps reside in the same exact folder as installer.iss
Source: "welcome_splash.bmp"; Flags: dontcopy
Source: "store_splash.bmp"; Flags: dontcopy

[Icons]
Name: "{userstartup}\AvvioPC Print Daemon"; Filename: "{app}\print_daemon.exe"
Name: "{group}\AvvioPC Print Daemon"; Filename: "{app}\print_daemon.exe"

[Run]
; Background execution trigger upon installer exit
Filename: "{app}\print_daemon.exe"; Flags: nowait runhidden

[Code]
// ==============================================================================
// 3. CUSTOM UI CONTROLS & JSON CONFIGURATION GENERATION
// ==============================================================================
var
  StorePage: TWizardPage;
  StoreComboBox: TComboBox;
  StoreDescLabel: TLabel;
  StoreImage: TBitmapImage;
  InfoTitleLabel, InfoBodyLabel: TLabel;

procedure UpdateStoreDescription(Sender: TObject);
var
  SelectedStore: String;
begin
  // Fetch current selection to evaluate label assignment
  SelectedStore := StoreComboBox.Items[StoreComboBox.ItemIndex];

  // Dynamic routing for descriptive labels based on retail network
  if SelectedStore = '000' then
    StoreDescLabel.Caption := '- Selezionare un negozio'
  else if SelectedStore = '040' then
    StoreDescLabel.Caption := '- Jesolo'
  else if SelectedStore = '054' then
    StoreDescLabel.Caption := '- Ballò di Mirano'
  else if SelectedStore = '281' then
    StoreDescLabel.Caption := '- Mestre Auchan'
  else if SelectedStore = '354' then
    StoreDescLabel.Caption := '- Oderzo Parco Stella'
  else
    StoreDescLabel.Caption := '';
end;

procedure InitializeWizard;
var
  ImagePath: String;
begin
  // Initialize custom wizard page for Store ID selection
  StorePage := CreateCustomPage(wpSelectDir, 'Configurazione Negozio', 'Impostazione del punto vendita.');

  // Extract the temporary image asset and assign the path
  ExtractTemporaryFile('store_splash.bmp');
  ImagePath := ExpandConstant('{tmp}\store_splash.bmp');

  // UI FIX: Il parent deve essere la tela grafica (Surface). 
  // Con Left e Top a 0 e l'altezza agganciata alla Surface, l'immagine toccherà il bordo sinistro.
  StoreImage := TBitmapImage.Create(StorePage);
  StoreImage.Parent := StorePage.Surface; 
  StoreImage.Left := 0;
  StoreImage.Top := 0;
  StoreImage.Width := ScaleX(145);  
  StoreImage.Height := StorePage.Surface.Height; 
  StoreImage.Stretch := True;
  
  try
    StoreImage.Bitmap.LoadFromFile(ImagePath);
  except
    Log('[WARNING] Store splash image missing or corrupted. Bypassing UI artwork render.');
  end;

  // Initialize rich text header (Title)
  InfoTitleLabel := TLabel.Create(StorePage);
  InfoTitleLabel.Parent := StorePage.Surface;
  InfoTitleLabel.Left := ScaleX(155); // Spostato leggermente a destra dell'immagine
  InfoTitleLabel.Top := ScaleY(10);
  InfoTitleLabel.Width := StorePage.Surface.Width - ScaleX(165); 
  InfoTitleLabel.Font.Style := [fsBold];
  InfoTitleLabel.Font.Size := 9;
  InfoTitleLabel.Caption := 'Parametri di base';

  // UI FIX: Testo multi-linea con a capo nativo in Pascal (#13#10)
  InfoBodyLabel := TLabel.Create(StorePage);
  InfoBodyLabel.Parent := StorePage.Surface;
  InfoBodyLabel.AutoSize := False; 
  InfoBodyLabel.WordWrap := True;
  InfoBodyLabel.Left := ScaleX(155);
  InfoBodyLabel.Top := ScaleY(40);
  InfoBodyLabel.Width := StorePage.Surface.Width - ScaleX(165);  
  InfoBodyLabel.Height := ScaleY(100); 
  InfoBodyLabel.Caption := 'Seleziona il codice identificativo del tuo negozio.' + #13#10 + #13#10 + 'Questa configurazione permetterà al servizio in background di intercettare e instradare correttamente i report generati dal server di AvvioPC per questo specifico punto vendita.';

  // Initialize dropdown component
  StoreComboBox := TComboBox.Create(StorePage);
  StoreComboBox.Parent := StorePage.Surface;
  StoreComboBox.Left := ScaleX(155); 
  StoreComboBox.Top := ScaleY(150);    
  StoreComboBox.Width := ScaleX(75);   
  StoreComboBox.Style := csDropDownList;
  
  // Bind the UI change event to the description updater
  StoreComboBox.OnChange := @UpdateStoreDescription;

  // Initialize description label component (Bolded for emphasis)
  StoreDescLabel := TLabel.Create(StorePage);
  StoreDescLabel.Parent := StorePage.Surface;
  StoreDescLabel.Left := StoreComboBox.Left + StoreComboBox.Width + ScaleX(10);
  StoreDescLabel.Top := StoreComboBox.Top + ScaleY(3);
  StoreDescLabel.Width := ScaleX(200);
  StoreDescLabel.Font.Style := [fsBold];
  StoreDescLabel.Caption := '';

  // Populate dropdown with exact Store IDs
  StoreComboBox.Items.Add('000');
  StoreComboBox.Items.Add('040');
  StoreComboBox.Items.Add('054');
  StoreComboBox.Items.Add('281');
  StoreComboBox.Items.Add('354');

  // Set default selected index
  StoreComboBox.ItemIndex := 0;

  // Initial trigger to render the default selection description
  UpdateStoreDescription(StoreComboBox);
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  SelectedStore: String;
  ConfigContent: String;
  ConfigFilePath: String;
begin
  // Execute JSON generation post-installation
  if CurStep = ssPostInstall then
  begin
    SelectedStore := StoreComboBox.Items[StoreComboBox.ItemIndex];
    ConfigFilePath := ExpandConstant('{app}\config.json');

    // Construct raw JSON string payload
    ConfigContent := '{' + #13#10 +
                     '    "store_id": "' + SelectedStore + '",' + #13#10 +
                     '    "target_printer": "",' + #13#10 +
                     '    "debug_mode": false' + #13#10 +
                     '}';

    // Write payload to configuration file
    if SaveStringToFile(ConfigFilePath, ConfigContent, False) then
      Log('[INFO] JSON configuration successfully generated.')
    else
      MsgBox('[CRITICAL] Failed to write configuration file during post-install sequence.', mbError, MB_OK);
  end;
end;